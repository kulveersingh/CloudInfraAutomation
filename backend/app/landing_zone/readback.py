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
    """A cloud's applied landing zone design, generated into that cloud's landing-zone repository."""

    kind = KIND
    input_file = INPUT_FILE

    def __init__(self, record: models.LandingZoneDesignRecord, render: Callable[[LandingZoneRequest], dict[str, str]],
                 repository: str = REPOSITORY_NAME):
        self._record = record
        self._render = render
        self._repository = repository

    @property
    def id(self):
        return str(self._record.id)

    @property
    def revision(self):
        return self._record.version

    @property
    def repository(self):
        return self._repository

    @property
    def recorded_commit(self):
        return self._record.commit_sha

    def recorded_request(self):
        return {"provider": self._record.provider, "answers": self._record.answers, "edits": self._record.edits}

    def parse_input(self, text):
        """design.json holds the answers and edits; the cloud is the record's (each cloud has its own repository)."""
        document = json.loads(text)
        request = LandingZoneRequest.model_validate({"provider": self._record.provider, "answers": document.get("answers"),
                                                     "edits": document.get("edits")})
        return {"provider": request.provider, "answers": request.answers.model_dump(mode="json"),
                "edits": TreeEditor.dump(request.edits)}

    def regenerate(self, request):
        return self._render(LandingZoneRequest.model_validate(request))
