from collections.abc import Iterator

from fastapi import Request
from sqlalchemy.orm import Session

from app.projects.service import ProjectService
from app.provisioning.queue import JobQueue
from app.registry.service import RegistryService


class ServiceContainer:
    """Per-request composition root: one database session and the services built on it."""

    def __init__(self, session: Session):
        self.registry = RegistryService.for_session(session)
        self.projects = ProjectService.for_session(session)
        self.jobs = JobQueue(session)

    @classmethod
    def provide(cls, request: Request) -> Iterator["ServiceContainer"]:
        with request.app.state.session_factory() as session:
            yield cls(session)
