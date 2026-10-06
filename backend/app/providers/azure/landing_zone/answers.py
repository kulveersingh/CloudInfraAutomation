from typing import Literal

from pydantic import BaseModel, Field

from app.landing_zone.answers import LandingZoneAnswers
from app.landing_zone.design import AccountPlan
from app.landing_zone.naming import UnitCatalog, UnitNamer

GUID = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
BILLING_ACCOUNT = r"/providers/Microsoft\.Billing/billingAccounts/[^/]+"
BILLING_SCOPE = (rf"^{BILLING_ACCOUNT}/(enrollmentAccounts/[^/]+"  # EA enrollment account
                 r"|billingProfiles/[^/]+/invoiceSections/[^/]+)$")  # MCA invoice section
ZERO = "00000000-0000-0000-0000-000000000000"
PREVIEW_ANSWERS = {"tenant_id": ZERO, "billing_scope": "/providers/Microsoft.Billing/billingAccounts/0/enrollmentAccounts/0",
                   "groups": {"platform_admins": ZERO, "network_admins": ZERO, "security_admins": ZERO,
                              "backup_super_users": ZERO}}


class AdminGroups(BaseModel):
    """Object ids of existing Entra groups that hold the landing zone's admin roles; the platform never creates
    groups."""

    platform_admins: str = Field(pattern=GUID)
    network_admins: str = Field(pattern=GUID)
    security_admins: str = Field(pattern=GUID)
    backup_super_users: str = Field(pattern=GUID)


class AzureLandingZoneAnswers(BaseModel):
    """What only the Azure landing zone asks (§22.12.3)."""

    tenant_id: str = Field(pattern=GUID)
    billing_scope: str = Field(pattern=BILLING_SCOPE)
    groups: AdminGroups
    defender: Literal["foundational", "standard"] = "foundational"
    firewall_tier: Literal["standard", "premium"] = "standard"


def azure_answers(answers: LandingZoneAnswers) -> AzureLandingZoneAnswers:
    return AzureLandingZoneAnswers.model_validate(answers.provider_answers)


class AzureSubscriptionNamer(UnitNamer):
    """Subscription names are only unique within the tenant, so each is "<org>-<suffix>", its alias too."""

    def __init__(self, answers: LandingZoneAnswers):
        self._organization = answers.organization_name

    def unit(self, suffix):
        return AccountPlan(name=f"{self._organization}-{suffix}")


# Nothing is pre-created on Azure. Spokes live in each workload subscription, so environments have no host (MC5-11).
AZURE_UNITS = UnitCatalog(security=("management", "security"), security_tooling="security-tooling",
                          infrastructure={"network": "connectivity", "shared_services": "shared-services",
                                          "identity": "identity", "backup": "backup", "monitoring": "monitoring"})


def root_detail(answers: LandingZoneAnswers) -> list[str]:
    return [f"Tenant {azure_answers(answers).tenant_id}", f"Management group {answers.organization_name}"]
