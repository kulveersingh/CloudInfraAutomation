from collections.abc import Callable

from app.db import models
from app.readback.manifest import Generator
from app.readback.subjects import ReadBackSubject
from app.synth.request import ProjectRequest
from app.synth.synthesizer import ENGINE_VERSION, GENERATOR_NAME

INPUT_FILE = "infra.json"
KIND = "project"
GENERATOR = Generator(name=GENERATOR_NAME, version=ENGINE_VERSION)
# A project starts at revision 1; each merged change (§21.8) adds one.
REVISION = 1


def repository_name(project_name: str) -> str:
    return f"{project_name}-infra"


class ProjectSubject(ReadBackSubject):
    """A provisioned project, generated into {project}-infra."""

    kind = KIND
    input_file = INPUT_FILE

    def __init__(self, project: models.Project, render: Callable[[ProjectRequest], dict[str, str]]):
        self._project = project
        self._render = render

    @property
    def id(self):
        return self._project.name

    @property
    def revision(self):
        return self._project.revision

    @property
    def repository(self):
        return repository_name(self._project.name)

    @property
    def recorded_commit(self):
        return self._project.commit_sha

    def recorded_request(self):
        return self._project.request

    def parse_input(self, text):
        return ProjectRequest.model_validate_json(text).model_dump(mode="json")

    def regenerate(self, request):
        return self._render(ProjectRequest.model_validate(request))
