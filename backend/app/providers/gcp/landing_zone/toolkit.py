from functools import cache

from app.landing_zone.toolkit import LandingZoneToolkit
from app.providers.gcp.landing_zone.answers import (
    GCP_UNITS,
    PREVIEW_ANSWERS,
    GcpLandingZoneAnswers,
    GcpProjectNamer,
    root_detail,
)
from app.providers.gcp.landing_zone.bundle import REPOSITORY_NAME, GcpLandingZoneBundle
from app.providers.gcp.landing_zone.controls import gcp_controls
from app.providers.gcp.landing_zone.limits import (
    DetectiveControlsNeedPremium,
    FoldersPerParent,
    MaximumFolderDepth,
    NoCentralEgress,
    ProjectIds,
    ProjectQuota,
    StrictResidencyBlocksDualRegionStorage,
)


@cache
def gcp_landing_zone() -> LandingZoneToolkit:
    """Folders and projects, Org Policy, IAM deny and Security Command Center, on Infrastructure Manager (§22.10)."""
    return LandingZoneToolkit(repository_name=REPOSITORY_NAME, bundle=GcpLandingZoneBundle(),
                              checks=(MaximumFolderDepth(), FoldersPerParent(), ProjectIds()),
                              advice=(DetectiveControlsNeedPremium(), NoCentralEgress(),
                                      StrictResidencyBlocksDualRegionStorage(), ProjectQuota()),
                              answers=GcpLandingZoneAnswers, namer=GcpProjectNamer, controls=gcp_controls(),
                              preview_answers=PREVIEW_ANSWERS, root_detail=root_detail, units=GCP_UNITS)
