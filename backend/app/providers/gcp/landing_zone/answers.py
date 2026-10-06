import hashlib
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.landing_zone.answers import LandingZoneAnswers
from app.landing_zone.design import AccountPlan
from app.landing_zone.naming import UnitCatalog, UnitNamer

GROUP_PATTERN = r"^[a-z0-9._-]+@[a-z0-9.-]+\.[a-z]{2,}$"
DOMAIN_PATTERN = r"^[a-z0-9-]+(\.[a-z0-9-]+)+$"
PROJECT_BASE_LENGTH = 25  # with "-" and 4 hex characters, a project id stays within Google Cloud's 30
PREVIEW_ANSWERS = {"organization_id": "123456789012", "billing_account": "000000-000000-000000",
                   "domain": "example.com"}


class AdminGroups(BaseModel):
    """Existing Cloud Identity groups that hold the landing zone's admin roles; the platform never creates groups."""

    organization_admins: str | None = Field(default=None, pattern=GROUP_PATTERN)
    network_admins: str | None = Field(default=None, pattern=GROUP_PATTERN)
    security_admins: str | None = Field(default=None, pattern=GROUP_PATTERN)
    billing_admins: str | None = Field(default=None, pattern=GROUP_PATTERN)
    backup_super_users: str | None = Field(default=None, pattern=GROUP_PATTERN)


class GcpLandingZoneAnswers(BaseModel):
    """What only the Google Cloud landing zone asks (§22.10.3)."""

    organization_id: str = Field(pattern=r"^[0-9]{1,20}$")
    billing_account: str = Field(pattern=r"^[0-9A-Z]{6}-[0-9A-Z]{6}-[0-9A-Z]{6}$")
    domain: str = Field(pattern=DOMAIN_PATTERN)
    groups: AdminGroups = Field(default_factory=AdminGroups)
    scc_tier: Literal["standard", "premium", "enterprise"] = "premium"

    @model_validator(mode="after")
    def default_groups(self) -> "GcpLandingZoneAnswers":
        """A group not named is `gcp-<role>@<domain>`."""
        named = {role: email or f"gcp-{role.replace('_', '-')}@{self.domain}"
                 for role, email in self.groups.model_dump().items()}
        self.groups = AdminGroups(**named)
        return self


def gcp_answers(answers: LandingZoneAnswers) -> GcpLandingZoneAnswers:
    return GcpLandingZoneAnswers.model_validate(answers.provider_answers)


class GcpProjectNamer(UnitNamer):
    """Project ids are global, so each is "<org>-<suffix>" kept to 25 characters, plus 4 hex characters of a hash
    of the organization id and the full name: unique across organizations, distinct when shortened (MC3-7)."""

    def __init__(self, answers: LandingZoneAnswers):
        self._organization = answers.organization_name
        self._organization_id = gcp_answers(answers).organization_id

    def unit(self, suffix):
        name = f"{self._organization}-{suffix}"
        digest = hashlib.sha1(f"{self._organization_id}:{name}".encode()).hexdigest()[:4]
        return AccountPlan(name=f"{name[:PROJECT_BASE_LENGTH].rstrip('-')}-{digest}")


# Nothing is pre-created on Google Cloud; Identity is Cloud Identity, so it has no project (§22.10.2).
GCP_UNITS = UnitCatalog(security=("logging", "security"), security_tooling="security-tooling",
                        infrastructure={"network": "net-hub", "shared_services": "shared-services", "backup": "vault",
                                        "monitoring": "monitoring"},
                        environment_host="net-{environment}")


def root_detail(answers: LandingZoneAnswers) -> list[str]:
    return [f"Organization {gcp_answers(answers).organization_id}", f"Seed project {answers.organization_name}-lz-seed"]
