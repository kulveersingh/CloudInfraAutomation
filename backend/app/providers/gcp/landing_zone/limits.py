from collections import Counter

from app.landing_zone.design import OuNode
from app.landing_zone.toolkit import LandingZoneCheck
from app.landing_zone.validation import DesignWarning
from app.providers.gcp.landing_zone.answers import gcp_answers

MAX_FOLDER_DEPTH = 10
MAX_FOLDERS_PER_PARENT = 300
PROJECT_ID_LENGTH = (6, 30)
PROJECT_QUOTA_HINT = 25
MAX_BUCKET_NAME = 63  # an organization starts with a small project quota
STRICT_RESIDENCY = "strict-residency"


class MaximumFolderDepth(LandingZoneCheck):
    def problems(self, design, catalog):
        return [f"Folder '{ou.name}' is {depth} levels deep; Google Cloud allows {MAX_FOLDER_DEPTH}."
                for ou, depth in _depths(design.root_ous, 1) if depth > MAX_FOLDER_DEPTH]


class FoldersPerParent(LandingZoneCheck):
    def problems(self, design, catalog):
        return [f"Folder '{ou.name}' has {len(ou.children)} folders; Google Cloud allows {MAX_FOLDERS_PER_PARENT} "
                "under one parent." for ou in design.walk() if len(ou.children) > MAX_FOLDERS_PER_PARENT]


class ProjectIds(LandingZoneCheck):
    """Project ids are 6 to 30 characters and, being global, must not repeat."""

    def problems(self, design, catalog):
        shortest, longest = PROJECT_ID_LENGTH
        names = [account.name for account in design.walk_accounts()]
        sizes = [f"Project id '{name}' is {len(name)} characters; Google Cloud allows {shortest} to {longest}."
                 for name in names if not shortest <= len(name) <= longest]
        return sizes + [f"Project id '{name}' is used twice." for name, total in Counter(names).items() if total > 1]


class VaultBucketNames(LandingZoneCheck):
    """Bucket names without dots are at most 63 characters."""

    def problems(self, design, catalog):
        from app.providers.gcp.landing_zone.deployments.vault import vault_bucket

        project = design.namer.unit(design.units.infrastructure["backup"]).name
        names = [vault_bucket(region, project) for region in design.answers.governed_regions]
        return [f"Vault bucket '{name}' is {len(name)} characters; Google Cloud allows {MAX_BUCKET_NAME}. Use a "
                "shorter organization name." for name in names if len(name) > MAX_BUCKET_NAME]


class DetectiveControlsNeedPremium(DesignWarning):
    def warnings(self, design):
        if gcp_answers(design.answers).scc_tier != "standard":
            return []
        return [("Detective controls are not deployed: Security Command Center Standard has no postures. "
                 "Choose Premium or Enterprise to deploy them.")]


class NoCentralEgress(DesignWarning):
    def warnings(self, design):
        if design.answers.network.egress != "central":
            return []
        return ["Google Cloud has no central egress VPC: each environment's VPC uses Cloud NAT."]


class StrictResidencyBlocksDualRegionStorage(DesignWarning):
    def warnings(self, design):
        if STRICT_RESIDENCY not in design.answers.packs():
            return []
        return [("Strict residency blocks dual-region buckets and multi-region Firestore, so DR/HA projects in these "
                 "folders cannot use them.")]


class ProjectQuota(DesignWarning):
    def warnings(self, design):
        total = len(design.accounts())
        if total <= PROJECT_QUOTA_HINT:
            return []
        return [(f"This design creates {total} projects; ask Google Cloud for a higher project quota before applying "
                 "(an organization starts with a small one).")]


def _depths(nodes: list[OuNode], depth: int) -> list[tuple[OuNode, int]]:
    return [pair for node in nodes for pair in ((node, depth), *_depths(node.children, depth + 1))]
