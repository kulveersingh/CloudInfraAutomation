from collections.abc import Iterator

from fastapi import Request
from sqlalchemy.orm import Session

from app.adapters.factory import AdapterFactory
from app.config import Settings
from app.projects.service import ProjectService
from app.provisioning.queue import JobQueue
from app.registry.service import RegistryService
from app.releases.service import ReleaseService


class ServiceContainer:
    """Per-request composition root: one database session and the services built on it."""

    def __init__(self, session: Session, settings: Settings):
        self.registry = RegistryService.for_session(session)
        self.projects = ProjectService.for_session(session)
        self.jobs = JobQueue(session)
        self.releases = ReleaseService.for_session(session, AdapterFactory().release_executor(settings))

    @classmethod
    def provide(cls, request: Request) -> Iterator["ServiceContainer"]:
        with request.app.state.session_factory() as session:
            yield cls(session, request.app.state.settings)
