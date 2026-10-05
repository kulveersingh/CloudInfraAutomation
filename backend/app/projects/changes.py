import uuid

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.adapters.ports import GitHubPort, MergeConflictError
from app.db import models
from app.errors import ConflictError, NotFoundError, ValidationFailedError
from app.projects.change_repository import ChangeState, ProjectChangeRepository
from app.projects.change_rules import ChangeRules
from app.projects.readback import repository_name
from app.projects.repository import ProjectRepository
from app.projects.service import ProjectService, pull_request_json
from app.provisioning.queue import JobQueue
from app.provisioning.states import ProjectStatus
from app.readback.manifest import MANIFEST_PATH
from app.registry.service import require
from app.synth.blocks.registry import BlockRegistry
from app.synth.request import ProjectRequest

CHANGE_JOB = "change"


class ChangeRequest(BaseModel):
    """A project's new request and the commit it was read back at (the optimistic lock, §21.8 C5)."""

    request: ProjectRequest
    base_commit: str
    confirm_removals: bool = False


class ProjectChangeService:
    """Change infrastructure (§21.8): preview, open as a change job that raises a pull request, merge or close."""

    def __init__(self, projects: ProjectRepository, changes: ProjectChangeRepository, service: ProjectService,
                 queue: JobQueue, github: GitHubPort, owner: str, blocks: BlockRegistry, rules: ChangeRules):
        self._projects = projects
        self._changes = changes
        self._service = service
        self._queue = queue
        self._github = github
        self._owner = owner
        self._blocks = blocks
        self._rules = rules

    @classmethod
    def for_session(cls, session: Session, github: GitHubPort, owner: str) -> "ProjectChangeService":
        return cls(ProjectRepository(session), ProjectChangeRepository(session), ProjectService.for_session(session),
                   JobQueue(session), github, owner, BlockRegistry.default(), ChangeRules.default())

    def preview(self, project_name: str, change: ChangeRequest) -> dict:
        project = self._changeable(project_name, change.request)
        return {**self._service.preview(change.request), "summary": self._summary(project, change.request)}

    def create(self, project_name: str, change: ChangeRequest, actor: str) -> dict:
        project = self._changeable(project_name, change.request)
        self._service.check(change.request)
        self._require_no_active_change(project)
        self._require_base(project, change.base_commit)
        summary = self._summary(project, change.request)
        deleted = [service["id"] for service in summary["removed_services"] if not service["retained"]]
        if deleted and not change.confirm_removals:
            raise ValidationFailedError(f"Removing {', '.join(deleted)} deletes its resources: confirm the removal.")
        revision = project.revision + 1
        record = models.ProjectChange(project_name=project.name, revision=revision,
                                      request=change.request.model_dump(mode="json"), summary=summary,
                                      base_commit=change.base_commit, branch=f"cloudinfra/change-{revision}",
                                      state=ChangeState.QUEUED, created_by=actor)
        self._changes.add(record)
        self._queue.enqueue(project.name, f"change-{record.id}", record.request, kind=CHANGE_JOB, change_id=record.id)
        return self._describe(record)

    def changes(self, project_name: str) -> list[dict]:
        self._project(project_name)
        return [self._describe(change) for change in self._changes.for_project(project_name)]

    def get(self, project_name: str, change_id: uuid.UUID) -> dict:
        return self._describe(self._change(project_name, change_id))

    def merge(self, project_name: str, change_id: uuid.UUID) -> dict:
        """Stands in for a person merging the pull request in GitHub (§21.8 C2)."""
        change = self._open_change(project_name, change_id)
        try:
            merge_commit = self._github.merge_pull_request(self._owner, repository_name(project_name),
                                                           change.pull_request_number)
        except MergeConflictError as error:
            raise ConflictError(str(error)) from error
        self.record_merge(change, merge_commit)
        return self._describe(change)

    def record_merge(self, change: models.ProjectChange, merge_commit: str) -> None:
        """The pull request was merged: the project is now at the change's revision."""
        project = self._projects.get(change.project_name)
        project.request, project.revision, project.commit_sha = change.request, change.revision, merge_commit
        change.state, change.merge_commit = ChangeState.MERGED, merge_commit
        self._changes.commit()

    def close(self, project_name: str, change_id: uuid.UUID) -> dict:
        change = self._open_change(project_name, change_id)
        self._github.close_pull_request(self._owner, repository_name(project_name), change.pull_request_number)
        change.state = ChangeState.CLOSED
        self._changes.commit()
        return self._describe(change)

    # ---- helpers ----

    def _project(self, project_name: str) -> models.Project:
        return require(self._projects.get(project_name), NotFoundError(f"Unknown project '{project_name}'."))

    def _changeable(self, project_name: str, request: ProjectRequest) -> models.Project:
        project = self._project(project_name)
        if project.status != ProjectStatus.ACTIVE:
            raise ConflictError(f"Project '{project_name}' is {project.status}; it can change once it is active.")
        problems = self._rules.problems(ProjectRequest.model_validate(project.request), request)
        if problems:
            raise ValidationFailedError(" ".join(problems))
        return project

    def _require_no_active_change(self, project: models.Project) -> None:
        active = self._changes.active(project.name)
        if active is not None:
            raise ConflictError(f"Change revision {active.revision} is still open: merge or close it first.")

    def _require_base(self, project: models.Project, base_commit: str) -> None:
        head = self._github.read_files(self._owner, repository_name(project.name)).commit_sha
        if base_commit != project.commit_sha or head != base_commit:
            raise ConflictError("The repository changed since you loaded it: load the project again and redo the "
                                "change.")

    def _change(self, project_name: str, change_id: uuid.UUID) -> models.ProjectChange:
        change = self._changes.get(change_id)
        if change is None or change.project_name != project_name:
            raise NotFoundError(f"Unknown change '{change_id}' for project '{project_name}'.")
        return change

    def _open_change(self, project_name: str, change_id: uuid.UUID) -> models.ProjectChange:
        change = self._change(project_name, change_id)
        if change.state != ChangeState.OPEN:
            raise ConflictError(f"Change revision {change.revision} is {change.state}, not open.")
        return change

    def _summary(self, project: models.Project, proposed: ProjectRequest) -> dict:
        current = ProjectRequest.model_validate(project.request)
        before = {resource.id: resource for resource in current.resources}
        after = {resource.id: resource for resource in proposed.resources}
        removed = [{"id": resource.id, "type": resource.type,
                    "retained": self._blocks.block_class(resource.type).retained_on_removal}
                   for resource in current.resources if resource.id not in after]
        repository = self._github.read_files(self._owner, repository_name(project.name)).files
        generated = self._service.render(proposed)
        return {"added_services": [resource.id for resource in proposed.resources if resource.id not in before],
                "removed_services": removed,
                "changed_services": [resource.id for resource in proposed.resources
                                     if resource.id in before and resource != before[resource.id]],
                "added_environments": [environment for environment in proposed.environments
                                       if environment not in current.environments],
                "changed_files": sorted(path for path, content in generated.items()
                                        if path != MANIFEST_PATH and repository.get(path) != content)}

    def _describe(self, change: models.ProjectChange) -> dict:
        job = self._queue.for_change(change.id)
        return {"id": str(change.id), "project_name": change.project_name, "revision": change.revision,
                "state": change.state, "base_commit": change.base_commit, "branch": change.branch,
                "pull_request": pull_request_json(change), "summary": change.summary,
                "created_by": change.created_by, "merge_commit": change.merge_commit,
                "job_id": str(job.id) if job else None, "created_at": change.created_at.isoformat()}
