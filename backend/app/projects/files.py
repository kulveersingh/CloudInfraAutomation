import json

from sqlalchemy.orm import Session

from app.projects.repository import ProjectRepository
from app.provisioning.states import ProjectStatus
from app.synth.binders.registry import BinderRegistry
from app.synth.blocks.registry import BlockRegistry
from app.synth.render import RepositoryBundle
from app.synth.request import ProjectRequest
from app.synth.synthesizer import TemplateSynthesizer
from app.teardown.records import TeardownRecords
from app.teardown.repository import TeardownRepository

DECOMMISSIONED_NOTICE = ("> This project was decommissioned: every environment was torn down after its data was backed "
                         "up into the locked vault. Restore it from the platform's Teardowns page.\n\n")


class ProjectFiles:
    """Everything the platform generates into a project's repository: the bundle, plus the teardown records and the
    decommission notice (§21.9.4), so read-back and regeneration see the same files the platform committed."""

    def __init__(self, bundle: RepositoryBundle, synthesizer: TemplateSynthesizer, projects: ProjectRepository,
                 teardowns: TeardownRepository):
        self._bundle = bundle
        self._synthesizer = synthesizer
        self._projects = projects
        self._teardowns = teardowns
        self._records = TeardownRecords(teardowns)

    @classmethod
    def for_session(cls, session: Session) -> "ProjectFiles":
        return cls(RepositoryBundle.default(), TemplateSynthesizer(BlockRegistry.default(), BinderRegistry.default()),
                   ProjectRepository(session), TeardownRepository(session))

    def render(self, request: ProjectRequest) -> dict[str, str]:
        files = self._bundle.render(request, self._synthesizer.synthesize(request))
        project = self._projects.get(request.project_name)
        if project is not None and project.status == ProjectStatus.DECOMMISSIONED:
            files["README.md"] = DECOMMISSIONED_NOTICE + files["README.md"]
        for teardown in self._teardowns.for_project(request.project_name):
            if self._records.committed(teardown):
                files[f"teardowns/{teardown.id}.json"] = json.dumps(self._records.record(teardown), indent=2,
                                                                     sort_keys=True) + "\n"
        return files
