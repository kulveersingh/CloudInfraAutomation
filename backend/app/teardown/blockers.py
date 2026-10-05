from abc import ABC, abstractmethod
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.db import models
from app.projects.change_repository import ProjectChangeRepository
from app.provisioning.states import ProjectStatus
from app.releases.repository import ReleaseRepository
from app.releases.state import ReleaseState
from app.teardown.repository import TeardownRepository
from app.teardown.states import TeardownScope

RELEASES_IN_PROGRESS = frozenset({ReleaseState.PLANNED, ReleaseState.OVERRIDE_REQUESTED,
                                  ReleaseState.AWAITING_APPROVAL, ReleaseState.DEPLOYING})


@dataclass(frozen=True)
class BlockerContext:
    project: models.Project
    environments: list[str]
    scope: str


class TeardownBlocker(ABC):
    """One reason a teardown cannot start now (§21.9.2). Add blockers to TeardownBlockers."""

    @abstractmethod
    def messages(self, context: BlockerContext) -> list[str]:
        ...


class ProjectActiveBlocker(TeardownBlocker):
    def messages(self, context):
        project = context.project
        if project.status == ProjectStatus.ACTIVE:
            return []
        return [f"Project '{project.name}' is {project.status}; only active projects can be torn down."]


class OpenChangeBlocker(TeardownBlocker):
    def __init__(self, changes: ProjectChangeRepository):
        self._changes = changes

    def messages(self, context):
        change = self._changes.active(context.project.name)
        return [] if change is None else [f"Change revision {change.revision} is still open: merge or close it first."]


class ActiveTeardownBlocker(TeardownBlocker):
    def __init__(self, teardowns: TeardownRepository):
        self._teardowns = teardowns

    def messages(self, context):
        if self._teardowns.active(context.project.name) is None:
            return []
        return [active_teardown_message(context.project.name)]


class ReleaseInProgressBlocker(TeardownBlocker):
    def __init__(self, releases: ReleaseRepository):
        self._releases = releases

    def messages(self, context):
        busy = {release.environment_id for release in self._releases.for_project(context.project.name)
                if release.state in RELEASES_IN_PROGRESS}
        return [f"A release to {environment} is in progress: finish or reject it first."
                for environment in context.environments if environment in busy]


class LastEnvironmentBlocker(TeardownBlocker):
    def messages(self, context):
        remaining = context.project.request["environments"]
        if context.scope == TeardownScope.ENVIRONMENT and len(remaining) == 1:
            return [f"{remaining[0]} is the project's last environment: decommission the project instead."]
        return []


class TeardownBlockers:
    def __init__(self, blockers: list[TeardownBlocker]):
        self._blockers = blockers

    @classmethod
    def for_session(cls, session: Session) -> "TeardownBlockers":
        return cls([ProjectActiveBlocker(), OpenChangeBlocker(ProjectChangeRepository(session)),
                    ActiveTeardownBlocker(TeardownRepository(session)),
                    ReleaseInProgressBlocker(ReleaseRepository(session)), LastEnvironmentBlocker()])

    def messages(self, context: BlockerContext) -> list[str]:
        return [message for blocker in self._blockers for message in blocker.messages(context)]


def active_teardown_message(project_name: str) -> str:
    return f"A teardown of {project_name} is in progress: finish it, or let its restore finish, first."
