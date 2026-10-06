from pydantic import BaseModel, Field

from app.landing_zone.answers import LandingZoneAnswers
from app.landing_zone.design import AccountPlan
from app.landing_zone.naming import UnitNamer

EMAIL_PATTERN = r"^[^@\s+]+@[^@\s]+\.[^@\s]+$"
PREVIEW_ANSWERS = {"management_email": "aws@example.com"}


class AwsLandingZoneAnswers(BaseModel):
    """What only the AWS landing zone asks: the management (payer) account's email."""

    management_email: str = Field(pattern=EMAIL_PATTERN)


class AwsAccountNamer(UnitNamer):
    """Account names are "<org>-<suffix>"; emails use plus addressing on the management mailbox."""

    def __init__(self, answers: LandingZoneAnswers):
        self._organization = answers.organization_name
        email = AwsLandingZoneAnswers.model_validate(answers.provider_answers).management_email
        self._local, self._domain = email.split("@")

    def unit(self, suffix):
        return AccountPlan(name=f"{self._organization}-{suffix}", email=f"{self._local}+{suffix}@{self._domain}")


def management_email(answers: LandingZoneAnswers) -> str:
    return AwsLandingZoneAnswers.model_validate(answers.provider_answers).management_email


def root_detail(answers: LandingZoneAnswers) -> list[str]:
    return ["Management / payer account", f"Control Tower {answers.home_region}"]
