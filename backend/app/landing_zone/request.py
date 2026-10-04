from pydantic import BaseModel, Field

from app.landing_zone.answers import LandingZoneAnswers
from app.landing_zone.edits import AnyTreeEdit


class LandingZoneRequest(BaseModel):
    """What the admin submits: the questionnaire answers and the OU tree editor's changes, in order."""

    answers: LandingZoneAnswers
    edits: list[AnyTreeEdit] = Field(default_factory=list)
