from pydantic import BaseModel, Field

from app.landing_zone.answers import LandingZoneAnswers
from app.landing_zone.design import AccountPlan
from app.landing_zone.naming import UnitCatalog, UnitNamer

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


# Control Tower creates the Security OU (Log Archive, Audit) and the Sandbox OU.
AWS_UNITS = UnitCatalog(security=("log-archive", "audit"), security_tooling="security-tooling",
                        infrastructure={"network": "network", "shared_services": "shared-services",
                                        "identity": "identity", "backup": "backup", "monitoring": "monitoring"},
                        created_by_service=frozenset({"security", "sandbox"}))


def network_host_suffix(answers: LandingZoneAnswers) -> str | None:
    """The account that owns the shared VPCs: Network, else Shared Services, else the management account (None)."""
    for key in ("network", "shared_services"):
        if key in answers.infrastructure:
            return AWS_UNITS.infrastructure[key]
    return None
