import uuid
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.adapters.ports import BOOTSTRAP_STACK, BackupPort, CloudPorts
from app.db import models
from app.errors import ConflictError, NotFoundError, ValidationFailedError
from app.landing_zone.repository import LandingZoneRepository
from app.projects.repository import ProjectRepository
from app.providers.base import ProviderRegistry
from app.provisioning.queue import JobQueue
from app.provisioning.states import ProjectStatus
from app.provisioning.topology import TopologyFactory
from app.registry.service import RegistryService, require
from app.releases.policy import Actor
from app.synth.request import ProjectRequest
from app.teardown.backup_account import BackupAccountResolver
from app.teardown.blockers import BlockerContext, TeardownBlockers
from app.teardown.inventory import DataStore
from app.teardown.policy import PLATFORM_ADMIN, REVIEWER, TeardownPolicy, approver_role
from app.teardown.records import TeardownRecords
from app.teardown.repository import TeardownRepository
from app.teardown.scheduler import TeardownScheduler
from app.teardown.states import EnvironmentState, RestoreState, TeardownScope, TeardownState, overall_state

RETENTION_DAYS = 60
NO_BACKUP_ACCOUNT = "No central Backup account is configured: add a Backup account to the landing zone first."
RESTORE_JOB = "restore"


class TeardownRequest(BaseModel):
    scope: Literal["environment", "project"]
    environments: list[str] = []
    confirmation: str = ""


@dataclass(frozen=True)
class PlannedEnvironment:
    environment: str
    position: int
    approver_role: str
    account_id: str
    regions: list[str]
    stores: list[DataStore]
    problems: list[str]


class TeardownService:
    """Teardown of an environment or a whole project (§21.9): preview, request, one approval per environment,
    retry, and restore from the teardown record."""

    def __init__(self, session: Session, clouds: CloudPorts, owner: str, backup_account: BackupAccountResolver):
        self._projects = ProjectRepository(session)
        self._teardowns = TeardownRepository(session)
        self._registry = RegistryService.for_session(session)
        self._topologies = TopologyFactory.default()
        self._providers = ProviderRegistry.default()
        self._blockers = TeardownBlockers.for_session(session)
        self._queue = JobQueue(session)
        self._scheduler = TeardownScheduler(self._teardowns, self._queue)
        self._records = TeardownRecords(self._teardowns)
        self._policy = TeardownPolicy()
        self._clouds = clouds
        self._owner = owner
        self._backup_account = backup_account

    @classmethod
    def for_session(cls, session: Session, clouds: CloudPorts, owner: str,
                    configured_backup_account: str | None) -> "TeardownService":
        return cls(session, clouds, owner, BackupAccountResolver(configured_backup_account,
                                                              LandingZoneRepository(session)))

    # ---- preview and request ----

    def preview(self, project_name: str, body: TeardownRequest) -> dict:
        project = self._project(project_name)
        planned = self._plan(project, body)
        request = ProjectRequest.model_validate(project.request)
        teardown = self._providers.get(project.provider).teardown()
        not_backed_up = [*teardown.inventory.not_backed_up(request), *teardown.notes]
        backup_account = self._backup_account.resolve()
        return {"scope": body.scope, "backup_account": backup_account, "retention_days": RETENTION_DAYS,
                "blockers": self._problems(project, body.scope, planned, backup_account),
                "environments": [{"environment": item.environment, "account_id": item.account_id,
                                  "regions": item.regions, "approver_role": item.approver_role,
                                  "stacks": [project.name, BOOTSTRAP_STACK.format(project=project.name)],
                                  "data_stores": [store.preview() for store in item.stores],
                                  "not_backed_up": not_backed_up} for item in planned]}

    def request(self, project_name: str, body: TeardownRequest, actor: Actor) -> dict:
        project = self._project(project_name)
        planned = self._plan(project, body)
        if body.confirmation != project.name:
            raise ValidationFailedError("Type the project name to confirm.")
        backup_account = self._backup_account.resolve()
        problems = self._problems(project, body.scope, planned, backup_account)
        if problems:
            raise ConflictError(" ".join(problems))
        teardown = models.Teardown(project_name=project.name, provider=project.provider, scope=body.scope, state=TeardownState.IN_PROGRESS,
                                   requested_by=actor.name, base_revision=project.revision,
                                   base_request=project.request, base_commit=project.commit_sha,
                                   backup_account_id=backup_account, restore_steps=[])
        self._teardowns.add(teardown, [models.TeardownEnvironment(
            environment=item.environment, position=item.position, approver_role=item.approver_role,
            account_id=item.account_id, regions=item.regions, state=EnvironmentState.PENDING_APPROVAL,
            completed_steps=[]) for item in planned])
        self._teardowns.commit()
        return self._records.describe(teardown)

    def teardowns(self) -> list[dict]:
        return [self._records.describe(teardown) for teardown in self._teardowns.all()]

    def for_project(self, project_name: str) -> list[dict]:
        self._project(project_name)
        return [self._records.describe(teardown) for teardown in self._teardowns.for_project(project_name)]

    def get(self, project_name: str, teardown_id: uuid.UUID) -> dict:
        return self._records.describe(self._teardown(project_name, teardown_id))

    # ---- one decision per environment ----

    def decide(self, project_name: str, teardown_id: uuid.UUID, environment: str, decision: str, actor: Actor,
               comment: str) -> dict:
        teardown = self._teardown(project_name, teardown_id)
        row = self._environment(teardown, environment)
        if decision == "retry":
            self._retry(teardown, row, actor)
        else:
            self._require_state(row, EnvironmentState.PENDING_APPROVAL)
            self._policy.require_approver(actor, row.approver_role, teardown.requested_by,
                                          f"tearing down {environment}",
                                          "You requested this teardown, so you cannot decide on it.")
            row.decided_by, row.decision_comment = actor.name, comment
            row.decided_at = models.utc_now()
            if decision == "approve":
                row.state = EnvironmentState.APPROVED
                self._scheduler.start_ready(teardown)
            else:
                self._reject(teardown, row)
        teardown.state = overall_state([item.state for item in self._teardowns.environments(teardown)])
        self._teardowns.commit()
        return self._records.describe(teardown)

    def _retry(self, teardown: models.Teardown, row: models.TeardownEnvironment, actor: Actor) -> None:
        self._require_state(row, EnvironmentState.FAILED)
        self._policy.require_approver(actor, row.approver_role, None, f"tearing down {row.environment}", "")
        self._scheduler.enqueue(teardown, row)

    def _reject(self, teardown: models.Teardown, row: models.TeardownEnvironment) -> None:
        """A rejected environment stays, and so do the others still waiting: the request stops there."""
        row.state = EnvironmentState.REJECTED
        for other in self._teardowns.environments(teardown):
            if other.state in EnvironmentState.WAITING:
                other.state = EnvironmentState.CANCELLED

    # ---- restore ----

    def restore(self, project_name: str, teardown_id: uuid.UUID, action: str, actor: Actor) -> dict:
        teardown = self._teardown(project_name, teardown_id)
        if action == "restore":
            self._request_restore(teardown, actor)
        else:
            self._decide_restore(teardown, action, actor)
        self._teardowns.commit()
        return self._records.describe(teardown)

    def _request_restore(self, teardown: models.Teardown, actor: Actor) -> None:
        completed = self._completed(teardown)
        if not completed:
            raise ConflictError("Nothing in this teardown was torn down, so there is nothing to restore.")
        if teardown.restore_state in RestoreState.ACTIVE:
            raise ConflictError("A restore of this teardown is already requested.")
        if teardown.restore_state == RestoreState.RESTORED:
            raise ConflictError("This teardown was already restored.")
        project = self._projects.get(teardown.project_name)
        backup = self._clouds.get(teardown.provider).backup(teardown.backup_account_id)
        for row in completed:
            self._require_restorable(project, row, backup)
        teardown.restore_state, teardown.restore_requested_by = RestoreState.REQUESTED, actor.name
        teardown.restore_decided_by, teardown.restore_steps = None, []

    def _require_restorable(self, project: models.Project, row: models.TeardownEnvironment, backup: BackupPort) -> None:
        if project.status != ProjectStatus.DECOMMISSIONED and row.environment in project.request["environments"]:
            raise ConflictError(f"{row.environment} exists in the project again, so it cannot be restored over.")
        for point in self._teardowns.recovery_points(row):
            if backup.recovery_point(point.recovery_point_ref) is None:
                raise ConflictError(f"The backup of {point.service_id} in {row.environment} ({point.region}) no "
                                    "longer exists, so it cannot be restored.")

    def _decide_restore(self, teardown: models.Teardown, action: str, actor: Actor) -> None:
        if teardown.restore_state != RestoreState.REQUESTED:
            raise ConflictError("No restore of this teardown is waiting for approval.")
        role = PLATFORM_ADMIN if any(row.approver_role == PLATFORM_ADMIN for row in self._completed(teardown)) \
            else REVIEWER
        self._policy.require_approver(actor, role, teardown.restore_requested_by, "this restore",
                                      "You requested this restore, so you cannot decide on it.")
        teardown.restore_decided_by = actor.name
        if action == "reject-restore":
            teardown.restore_state = RestoreState.REJECTED
            return
        job = self._queue.enqueue(teardown.project_name, f"restore-{uuid.uuid4()}",
                                  {"teardown_id": str(teardown.id), "provider": teardown.provider}, kind=RESTORE_JOB)
        teardown.restore_state, teardown.restore_job_id = RestoreState.QUEUED, job.id

    # ---- helpers ----

    def _project(self, project_name: str) -> models.Project:
        return require(self._projects.get(project_name), NotFoundError(f"Unknown project '{project_name}'."))

    def _teardown(self, project_name: str, teardown_id: uuid.UUID) -> models.Teardown:
        teardown = self._teardowns.get(teardown_id)
        if teardown is None or teardown.project_name != project_name:
            raise NotFoundError(f"Unknown teardown '{teardown_id}' for project '{project_name}'.")
        return teardown

    def _environment(self, teardown: models.Teardown, environment: str) -> models.TeardownEnvironment:
        return require(next((row for row in self._teardowns.environments(teardown) if row.environment == environment),
                            None), NotFoundError(f"Teardown {teardown.id} has no environment '{environment}'."))

    def _completed(self, teardown: models.Teardown) -> list[models.TeardownEnvironment]:
        return [row for row in self._teardowns.environments(teardown) if row.state == EnvironmentState.COMPLETED]

    def _require_state(self, row: models.TeardownEnvironment, state: str) -> None:
        if row.state != state:
            raise ConflictError(f"{row.environment} is {row.state}, not {state}.")

    def _plan(self, project: models.Project, body: TeardownRequest) -> list[PlannedEnvironment]:
        request = ProjectRequest.model_validate(project.request)
        environments = self._chosen(project, request, body)
        catalog = {environment["id"]: environment for environment in self._registry.environments()}
        environments.sort(key=lambda environment: catalog[environment]["position"])
        accounts = self._registry.target_accounts(request.provider, request.ownership.portfolio_id, environments)
        topology = self._topologies.for_resilience(request.resilience)
        inventory = self._providers.get(project.provider).teardown().inventory
        planned = []
        for environment in environments:
            regions = topology.regions_for(environment)
            stores, problems = inventory.for_environment(request, environment, accounts[environment], regions)
            planned.append(PlannedEnvironment(environment, catalog[environment]["position"],
                                              approver_role(catalog[environment]["requires_approval"]),
                                              accounts[environment], regions, stores, problems))
        return planned

    def _chosen(self, project: models.Project, request: ProjectRequest, body: TeardownRequest) -> list[str]:
        if body.scope == TeardownScope.PROJECT:
            return list(request.environments)
        if len(body.environments) != 1:
            raise ValidationFailedError("Choose exactly one environment to tear down.")
        [environment] = body.environments
        if environment not in request.environments:
            raise ValidationFailedError(f"{project.name} has no environment '{environment}'.")
        return [environment]

    def _problems(self, project: models.Project, scope: str, planned: list[PlannedEnvironment],
                  backup_account: str | None) -> list[str]:
        context = BlockerContext(project, [item.environment for item in planned], scope)
        problems = [*self._blockers.messages(context), *[problem for item in planned for problem in item.problems]]
        problems = list(dict.fromkeys(problems))
        return problems if backup_account else [*problems, NO_BACKUP_ACCOUNT]
