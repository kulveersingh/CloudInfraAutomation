import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy.orm import Session

from app.adapters.ports import AwsPort, BackupPort, BackupSource, BootstrapRequest, GitHubPort
from app.db import models
from app.projects.files import ProjectFiles
from app.projects.readback import GENERATOR, INPUT_FILE, KIND, repository_name
from app.projects.repository import ProjectRepository
from app.provisioning.queue import JobQueue
from app.provisioning.runner import JobRunner
from app.provisioning.states import JobState, ProjectStatus, StepState
from app.provisioning.steps import ConfigureEnvironmentsStep, ExistingBootstrapStep
from app.readback.manifest import MANIFEST_PATH, ManifestSealer, ManifestSigner
from app.readback.subjects import ownership_properties
from app.synth.request import ProjectRequest
from app.teardown.inventory import DataStore, DataStoreInventory
from app.teardown.repository import TeardownRepository
from app.teardown.scheduler import TeardownScheduler
from app.teardown.states import EnvironmentState, RestoreState, TeardownScope, TeardownState, overall_state

RETENTION = timedelta(days=60)
STATE_PROPERTY = "cloudinfra-state"


@dataclass(frozen=True)
class Step:
    key: str
    run: Callable[[], None]


class Checkpoints:
    """Runs steps forward only (deletions cannot be undone): finished steps are recorded and skipped on retry."""

    def __init__(self, queue: JobQueue, teardowns: TeardownRepository):
        self._queue = queue
        self._teardowns = teardowns

    def run(self, job: models.Job, steps: list[Step], done: list[str],
            save: Callable[[list[str]], None]) -> str | None:
        finished = list(done)
        for step in steps:
            if step.key in finished:
                continue
            try:
                step.run()
            except Exception as error:  # noqa: BLE001 - any failure stops the job for a person to look at
                self._teardowns.rollback()
                self._queue.record_step(job, step.key, StepState.FAILED, str(error))
                return str(error)
            finished = [*finished, step.key]
            save(finished)
            self._queue.record_step(job, step.key, StepState.SUCCEEDED)
        return None


class RepositoryCommitter:
    """Commits a project's files at its next revision, sealed, removing generated files it no longer has."""

    def __init__(self, github: GitHubPort, owner: str, signer: ManifestSigner, files: ProjectFiles):
        self._github = github
        self._owner = owner
        self._signer = signer
        self._sealer = ManifestSealer(signer)
        self._files = files

    def commit(self, project: models.Project, request: ProjectRequest, message: str) -> None:
        revision = project.revision + 1
        repository = repository_name(project.name)
        current = self._github.read_files(self._owner, repository).files
        before = set(self._signer.verify(json.loads(current[MANIFEST_PATH])).files)
        files = self._files.render(request)
        sealed = self._sealer.seal(kind=KIND, id=project.name, revision=revision, generator=GENERATOR,
                                   input=INPUT_FILE, files=files)
        sha = self._github.commit_files(self._owner, repository, sealed, message, deleted=sorted(before - set(files)))
        project.request, project.revision, project.commit_sha = request.model_dump(mode="json"), revision, sha


class TeardownJobRunner:
    """Tears down one approved environment (§21.9.2): locked backups first, then stacks, data, bootstrap, GitHub,
    and the next revision; a decommission's last environment also archives the repository."""

    def __init__(self, session: Session, github: GitHubPort, aws: AwsPort, owner: str, signer: ManifestSigner):
        self._teardowns = TeardownRepository(session)
        self._projects = ProjectRepository(session)
        self._queue = JobQueue(session)
        self._scheduler = TeardownScheduler(self._teardowns, self._queue)
        self._checkpoints = Checkpoints(self._queue, self._teardowns)
        self._inventory = DataStoreInventory.default()
        self._committer = RepositoryCommitter(github, owner, signer, ProjectFiles.for_session(session))
        self._github = github
        self._aws = aws
        self._owner = owner

    @classmethod
    def for_session(cls, session: Session, github: GitHubPort, aws: AwsPort, owner: str,
                    signer: ManifestSigner) -> "TeardownJobRunner":
        return cls(session, github, aws, owner, signer)

    def run(self, job: models.Job) -> None:
        row = self._teardowns.environment(uuid.UUID(job.payload["teardown_environment_id"]))
        teardown = self._teardowns.get(row.teardown_id)
        row.state = EnvironmentState.RUNNING
        self._teardowns.commit()
        error = self._checkpoints.run(job, self._steps(teardown, row), row.completed_steps,
                                      lambda finished: setattr(row, "completed_steps", finished))
        if error is not None:
            row.state, row.error = EnvironmentState.FAILED, error
        self._queue.finish(job, JobState.FAILED_NEEDS_ATTENTION if error else JobState.SUCCEEDED, error)
        teardown.state = overall_state([item.state for item in self._teardowns.environments(teardown)])
        self._scheduler.start_ready(teardown)
        self._teardowns.commit()

    def _steps(self, teardown: models.Teardown, row: models.TeardownEnvironment) -> list[Step]:
        project = self._projects.get(teardown.project_name)
        request = ProjectRequest.model_validate(project.request)
        stores, _ = self._inventory.for_environment(request, row.environment, row.account_id, row.regions)
        backup = self._aws.backup(teardown.backup_account_id)
        regions = [region for region in row.regions if any(store.region == region for store in stores)]
        steps = [Step(f"vault:{region}", lambda region=region: _require_locked(backup, region)) for region in regions]
        steps += [Step(f"backup:{store.region}:{store.service_id}",
                       lambda store=store: self._back_up(backup, row, store)) for store in stores]
        steps.append(Step("verify-backups", lambda: self._verify(backup, row, stores)))
        for region in reversed(row.regions):  # the secondary region goes first
            steps += self._delete_region(project, row, region, [store for store in stores if store.region == region])
        steps += [Step(f"delete-bootstrap:{region}", lambda region=region: self._aws.delete_bootstrap_stack(
            self._bootstrap(project, row, region))) for region in row.regions]
        steps.append(Step("github-environment", lambda: self._remove_github_environment(project, row)))
        steps.append(Step("commit", lambda: self._commit(teardown, row, project)))
        steps.append(Step("finish", lambda: self._finish(teardown, project)))
        return steps

    def _back_up(self, backup: BackupPort, row: models.TeardownEnvironment, store: DataStore) -> None:
        point = backup.back_up(BackupSource(row.account_id, store.region, store.resource_type, store.source_arn))
        self._teardowns.add_recovery_point(models.TeardownRecoveryPoint(
            teardown_environment_id=row.id, service_id=store.service_id, logical_id=store.logical_id,
            resource_type=store.resource_type, physical_name=store.physical_name, region=store.region,
            account_id=point.account_id, recovery_point_arn=point.arn, vault=point.vault,
            completed_at=point.completed_at, locked_until=point.locked_until))

    def _verify(self, backup: BackupPort, row: models.TeardownEnvironment, stores: list[DataStore]) -> None:
        """Every data store has a completed backup in the locked vault before anything is deleted."""
        kept = {(point.service_id, point.region): backup.recovery_point(point.recovery_point_arn)
                for point in self._teardowns.recovery_points(row)}
        missing = [store for store in stores if not _locked(kept.get((store.service_id, store.region)))]
        if missing:
            names = ", ".join(f"{store.service_id} ({store.region})" for store in missing)
            raise RuntimeError(f"No locked backup in the central vault for {names}; nothing was deleted.")

    def _delete_region(self, project: models.Project, row: models.TeardownEnvironment, region: str,
                       stores: list[DataStore]) -> list[Step]:
        account = row.account_id
        steps = [Step(f"allow-deletion:{region}", lambda: self._aws.allow_stack_deletion(account, region, project.name)),
                 Step(f"delete-stack:{region}", lambda: self._aws.delete_stack(account, region, project.name))]
        return steps + [Step(f"delete-data:{region}:{store.service_id}",
                             lambda store=store: self._aws.delete_data_store(account, region, store.resource_type,
                                                                             store.physical_name))
                        for store in stores if store.retained]

    def _bootstrap(self, project: models.Project, row: models.TeardownEnvironment, region: str) -> BootstrapRequest:
        return BootstrapRequest(account_id=row.account_id, region=region, project=project.name,
                                repository=f"{self._owner}/{repository_name(project.name)}",
                                environment=row.environment)

    def _remove_github_environment(self, project: models.Project, row: models.TeardownEnvironment) -> None:
        repository = repository_name(project.name)
        self._github.delete_environment(self._owner, repository, row.environment)
        variables = self._github.repository_variables(self._owner, repository)
        order = [environment for environment in variables["ENVIRONMENT_ORDER"].split(",")
                 if environment != row.environment]
        self._github.set_repository_variables(self._owner, repository,
                                              {**variables, "ENVIRONMENT_ORDER": ",".join(order)})

    def _commit(self, teardown: models.Teardown, row: models.TeardownEnvironment, project: models.Project) -> None:
        current = ProjectRequest.model_validate(project.request)
        remaining = [environment for environment in current.environments if environment != row.environment]
        # The last environment of a decommission stays in infra.json: the final design is what a restore starts from.
        request = current.model_copy(update={"environments": remaining}) if remaining else current
        row.state, row.revision = EnvironmentState.COMPLETED, project.revision + 1
        teardown.state = overall_state([item.state for item in self._teardowns.environments(teardown)])
        if teardown.scope == TeardownScope.PROJECT and teardown.state == TeardownState.COMPLETED:
            project.status = ProjectStatus.DECOMMISSIONED
        self._committer.commit(project, request, f"Tear down {row.environment} (revision {row.revision})")

    def _finish(self, teardown: models.Teardown, project: models.Project) -> None:
        if project.status != ProjectStatus.DECOMMISSIONED:
            return
        repository = repository_name(project.name)
        self._github.set_repository_properties(self._owner, repository, {
            **ownership_properties(KIND, project.name), STATE_PROPERTY: ProjectStatus.DECOMMISSIONED})
        self._github.archive_repository(self._owner, repository)


class RestoreJobRunner:
    """Restores what a teardown removed (§21.9.5): bootstrap, data from the locked backups, an IMPORT stack, GitHub
    environments, and the next revision with the environments back."""

    def __init__(self, session: Session, github: GitHubPort, aws: AwsPort, owner: str, signer: ManifestSigner):
        self._teardowns = TeardownRepository(session)
        self._projects = ProjectRepository(session)
        self._queue = JobQueue(session)
        self._checkpoints = Checkpoints(self._queue, self._teardowns)
        self._provisioning = JobRunner.for_session(session, github, aws, owner, signer)
        self._committer = RepositoryCommitter(github, owner, signer, ProjectFiles.for_session(session))
        self._github = github
        self._aws = aws
        self._owner = owner

    @classmethod
    def for_session(cls, session: Session, github: GitHubPort, aws: AwsPort, owner: str,
                    signer: ManifestSigner) -> "RestoreJobRunner":
        return cls(session, github, aws, owner, signer)

    def run(self, job: models.Job) -> None:
        teardown = self._teardowns.get(uuid.UUID(job.payload["teardown_id"]))
        teardown.restore_state = RestoreState.RUNNING
        self._teardowns.commit()
        error = self._checkpoints.run(job, self._steps(teardown, job), teardown.restore_steps,
                                      lambda finished: setattr(teardown, "restore_steps", finished))
        if error is not None:
            teardown.restore_state = RestoreState.FAILED
        self._queue.finish(job, JobState.FAILED_NEEDS_ATTENTION if error else JobState.SUCCEEDED, error)
        self._teardowns.commit()

    def _steps(self, teardown: models.Teardown, job: models.Job) -> list[Step]:
        project = self._projects.get(teardown.project_name)
        rows = [row for row in self._teardowns.environments(teardown) if row.state == EnvironmentState.COMPLETED]
        backup = self._aws.backup(teardown.backup_account_id)
        steps = [Step("reactivate", lambda: self._reactivate(project))]
        for row in rows:
            steps += [Step(f"bootstrap:{row.environment}:{region}",
                           lambda row=row, region=region: self._aws.ensure_bootstrap_stack(BootstrapRequest(
                               account_id=row.account_id, region=region, project=project.name,
                               repository=f"{self._owner}/{repository_name(project.name)}",
                               environment=row.environment))) for region in row.regions]
            points = self._teardowns.recovery_points(row)
            steps += [Step(f"restore:{row.environment}:{point.region}:{point.service_id}",
                           lambda row=row, point=point: backup.restore(point.recovery_point_arn, row.account_id,
                                                                       point.region, point.physical_name))
                      for point in points]
            for region in dict.fromkeys(point.region for point in points):
                logical_ids = [point.logical_id for point in points if point.region == region]
                steps.append(Step(f"import:{row.environment}:{region}",
                                  lambda row=row, region=region, logical_ids=logical_ids: self._aws.import_stack(
                                      row.account_id, region, project.name, logical_ids)))
        request = self._restored_request(teardown, project, rows)
        steps.append(Step("configure-environments", lambda: self._configure(job, request, project)))
        steps.append(Step("commit", lambda: self._commit(teardown, project, request)))
        return steps

    def _reactivate(self, project: models.Project) -> None:
        if project.status != ProjectStatus.DECOMMISSIONED:
            return
        repository = repository_name(project.name)
        self._github.unarchive_repository(self._owner, repository)
        self._github.set_repository_properties(self._owner, repository, {
            **ownership_properties(KIND, project.name), STATE_PROPERTY: ProjectStatus.ACTIVE})
        project.status = ProjectStatus.ACTIVE

    def _restored_request(self, teardown: models.Teardown, project: models.Project,
                          rows: list[models.TeardownEnvironment]) -> ProjectRequest:
        current = ProjectRequest.model_validate(project.request)
        wanted = {*current.environments, *(row.environment for row in rows)}
        order = [environment for environment in teardown.base_request["environments"] if environment in wanted]
        return current.model_copy(update={"environments": order})

    def _configure(self, job: models.Job, request: ProjectRequest, project: models.Project) -> None:
        context = self._provisioning.context(job.request_id, request, project.revision + 1)
        for environment in request.environments:
            for region in context.topology.regions_for(environment):
                ExistingBootstrapStep(environment, region).execute(context)
        ConfigureEnvironmentsStep().execute(context)

    def _commit(self, teardown: models.Teardown, project: models.Project, request: ProjectRequest) -> None:
        teardown.restore_state = RestoreState.RESTORED
        self._committer.commit(project, request, f"Restore after teardown {teardown.id} (revision {project.revision + 1})")


def _require_locked(backup: BackupPort, region: str) -> None:
    lock = backup.vault_lock(region)
    if not lock.locked or lock.min_retention_days < RETENTION.days:
        raise RuntimeError(f"The central vault cloudinfra-teardown-{region} is not locked for at least "
                           f"{RETENTION.days} days.")


def _locked(point) -> bool:
    return point is not None and point.locked_until - point.completed_at >= RETENTION
