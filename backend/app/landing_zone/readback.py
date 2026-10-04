import json
from collections.abc import Callable

from app.db import models
from app.landing_zone.edits import TreeEditor
from app.landing_zone.request import LandingZoneRequest
from app.readback.manifest import Generator
from app.readback.subjects import ReadBackSubject

REPOSITORY_NAME = "landing-zone-infra"
INPUT_FILE = "design.json"
KIND = "landing-zone"
GENERATOR = Generator(name="cloudinfra-landing-zone", version="0.1.0")


class LandingZoneSubject(ReadBackSubject):
    """The applied landing zone design, generated into landing-zone-infra."""

    kind = KIND
    input_file = INPUT_FILE

    def __init__(self, record: models.LandingZoneDesignRecord, render: Callable[[LandingZoneRequest], dict[str, str]]):
        self._record = record
        self._render = render

    @property
    def id(self):
        return str(self._record.id)

    @property
    def revision(self):
        return self._record.version

    @property
    def repository(self):
        return REPOSITORY_NAME

    @property
    def recorded_commit(self):
        return self._record.commit_sha

    def recorded_request(self):
        return {"answers": self._record.answers, "edits": self._record.edits}

    def parse_input(self, text):
        document = json.loads(text)
        request = LandingZoneRequest.model_validate({"answers": document.get("answers"),
                                                     "edits": document.get("edits")})
        return {"answers": request.answers.model_dump(mode="json"), "edits": TreeEditor.dump(request.edits)}

    def regenerate(self, request):
        return self._render(LandingZoneRequest.model_validate(request))
