from app.landing_zone.design import OuNode
from app.landing_zone.toolkit import LandingZoneCheck
from app.landing_zone.validation import DesignWarning
from app.providers.aws.landing_zone.cloudformation.guardrails import GuardrailPlan, ScpQuotaRule

MAX_OU_DEPTH = 5
# Control Tower registers an OU of up to this many accounts, by the number of governed Regions.
REGISTRATION_LIMITS = [(15, 1000), (21, 600)]
REGISTRATION_LIMIT_BEYOND = 680
STRICT_RESIDENCY = "strict-residency"


class MaximumDepth(LandingZoneCheck):
    def problems(self, design, catalog):
        return [f"OU '{ou.name}' is {depth} levels deep; AWS Organizations allows {MAX_OU_DEPTH}."
                for ou, depth in _depths(design.root_ous, 1) if depth > MAX_OU_DEPTH]


class ScpQuotaCheck(LandingZoneCheck):
    def problems(self, design, catalog):
        return ScpQuotaRule().problems(GuardrailPlan.for_design(design))


class OuSizeWithinRegistrationLimit(DesignWarning):
    def warnings(self, design):
        regions = len(design.answers.governed_regions)
        limit = next((size for most, size in REGISTRATION_LIMITS if regions <= most), REGISTRATION_LIMIT_BEYOND)
        return [f"OU '{ou.name}' plans {len(ou.accounts)} accounts; AWS Control Tower registers OUs of up to {limit} "
                f"with {regions} governed Regions." for ou in design.walk() if len(ou.accounts) > limit]


def _depths(nodes: list[OuNode], depth: int) -> list[tuple[OuNode, int]]:
    return [pair for node in nodes for pair in ((node, depth), *_depths(node.children, depth + 1))]


class StrictResidencyBlocksReplication(DesignWarning):
    def warnings(self, design):
        if STRICT_RESIDENCY not in design.answers.packs():
            return []
        return [("Strict residency blocks S3 cross-Region replication, so DR/HA projects in these OUs cannot "
                 "replicate S3 buckets.")]
