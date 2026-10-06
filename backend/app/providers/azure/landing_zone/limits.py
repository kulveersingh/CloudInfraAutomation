from collections import Counter

from app.landing_zone.design import OuNode
from app.landing_zone.toolkit import LandingZoneCheck
from app.landing_zone.validation import DesignWarning
from app.providers.azure.landing_zone.answers import azure_answers

MAX_DEPTH_BELOW_ROOT = 6
MAX_MANAGEMENT_GROUP_ID = 90
MAX_SUBSCRIPTION_NAME = 64
MAX_ASSIGNMENTS_PER_SCOPE = 200
SUBSCRIPTION_HINT = 20
STRICT_RESIDENCY = "strict-residency"


class ManagementGroupDepth(LandingZoneCheck):
    """The organization's own management group is the first level below the tenant root (MC5-3)."""

    def problems(self, design, catalog):
        return [f"Management group '{ou.name}' is {depth} levels below the tenant root; Azure allows "
                f"{MAX_DEPTH_BELOW_ROOT}." for ou, depth in _depths(design.root_ous, 2) if depth > MAX_DEPTH_BELOW_ROOT]


class ManagementGroupIds(LandingZoneCheck):
    def problems(self, design, catalog):
        ids = [management_group_id(design.answers.organization_name, ou) for ou in design.walk()]
        return [f"Management group id '{group}' is {len(group)} characters; Azure allows {MAX_MANAGEMENT_GROUP_ID}."
                for group in ids if len(group) > MAX_MANAGEMENT_GROUP_ID]


class SubscriptionNames(LandingZoneCheck):
    """Names are subscription aliases, unique in the tenant."""

    def problems(self, design, catalog):
        names = [account.name for account in design.walk_accounts()]
        sizes = [f"Subscription name '{name}' is {len(name)} characters; Azure allows {MAX_SUBSCRIPTION_NAME}."
                 for name in names if len(name) > MAX_SUBSCRIPTION_NAME]
        return sizes + [f"Subscription name '{name}' is used twice." for name, total in Counter(names).items()
                        if total > 1]


class PairedGovernedRegions(LandingZoneCheck):
    """Geo-redundant storage replicates only to a region's pair (MC4-4), so the design governs both. Designs always
    govern at least two regions."""

    def __init__(self, pairs: dict[str, str]):
        self._pairs = pairs

    def problems(self, design, catalog):
        governed = design.answers.governed_regions
        return [f"Governed region {region} pairs with {self._pairs[region]}, which is not governed: geo-redundant "
                "storage there cannot replicate for DR and HA." for region in governed
                if region in self._pairs and self._pairs[region] not in governed]


class PolicyAssignmentsPerScope(LandingZoneCheck):
    def __init__(self, limit: int = MAX_ASSIGNMENTS_PER_SCOPE):
        self._limit = limit

    def problems(self, design, catalog):
        from app.providers.azure.landing_zone.toolkit import azure_landing_zone

        controls = azure_landing_zone().resolver().resolve(design).controls
        return [f"Management group '{ou.name}' gets {len(controls[ou.key])} policy assignments; Azure allows "
                f"{self._limit} per scope." for ou in design.walk() if len(controls.get(ou.key, [])) > self._limit]


class DefenderPlansCost(DesignWarning):
    def warnings(self, design):
        if azure_answers(design.answers).defender != "standard":
            return []
        return [(f"Defender plans are billed per subscription and protected resource: this design enables them on "
                 f"{len(design.accounts())} subscriptions.")]


class LocalEgressSkipsFirewall(DesignWarning):
    def warnings(self, design):
        if design.answers.network.egress != "local":
            return []
        return ["Local egress uses a NAT gateway in each spoke, so outbound traffic does not pass the hub's firewall."]


class StrictResidencyAgainstPairs(DesignWarning):
    def warnings(self, design):
        if STRICT_RESIDENCY not in design.answers.packs():
            return []
        return [("Strict residency denies geo-redundant storage whose pair is outside the governed regions, so DR/HA "
                 "projects with storage need both regions of a pair governed.")]


class IdentityOnlyForDomainControllers(DesignWarning):
    def warnings(self, design):
        if "identity" not in design.answers.infrastructure:
            return []
        return ["The Identity subscription is only needed for AD DS domain controllers; Entra ID needs none."]


class SubscriptionCreationLimits(DesignWarning):
    def warnings(self, design):
        total = len(design.accounts())
        if total <= SUBSCRIPTION_HINT:
            return []
        return [(f"This design creates {total} subscriptions; billing accounts limit how many can be created, so ask "
                 "for room on the billing account before applying.")]


def management_group_id(organization: str, ou: OuNode) -> str:
    return f"{organization}-{ou.key.replace('_', '-')}"


def _depths(nodes: list[OuNode], depth: int) -> list[tuple[OuNode, int]]:
    return [pair for node in nodes for pair in ((node, depth), *_depths(node.children, depth + 1))]
