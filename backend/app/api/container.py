from collections.abc import Iterator

from fastapi import Request
from sqlalchemy.orm import Session

from app.adapters.factory import AdapterFactory
from app.config import Settings
from app.landing_zone.service import LandingZoneService
from app.networks.service import NetworkService
from app.projects.changes import ProjectChangeService
from app.projects.service import ProjectService
from app.provisioning.queue import JobQueue
from app.readback.manifest import ManifestSigner
from app.readback.reader import RepositoryReader
from app.registry.service import RegistryService
from app.releases.service import ReleaseService


class ServiceContainer:
    """Per-request composition root: one database session and the services built on it."""

    def __init__(self, session: Session, settings: Settings):
        self.registry = RegistryService.for_session(session)
        self.projects = ProjectService.for_session(session)
        self.jobs = JobQueue(session)
        self.networks = NetworkService.for_session(session)
        adapters = AdapterFactory()
        github, signer = adapters.github(settings), ManifestSigner.from_settings(settings)
        self.releases = ReleaseService.for_session(session, adapters.release_executor(settings))
        self.landing_zone = LandingZoneService.for_session(session, github, adapters.landing_zone_executor(settings),
                                                           settings.github_owner, signer)
        self.read_back = RepositoryReader.default(github, settings.github_owner, signer)
        self.project_changes = ProjectChangeService.for_session(session, github, settings.github_owner)

    @classmethod
    def provide(cls, request: Request) -> Iterator["ServiceContainer"]:
        with request.app.state.session_factory() as session:
            yield cls(session, request.app.state.settings)
