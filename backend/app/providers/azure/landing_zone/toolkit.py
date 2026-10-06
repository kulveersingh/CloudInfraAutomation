from functools import cache

from app.landing_zone.toolkit import LandingZoneToolkit
from app.providers.azure.landing_zone.answers import (
    AZURE_UNITS,
    PREVIEW_ANSWERS,
    AzureLandingZoneAnswers,
    AzureSubscriptionNamer,
    root_detail,
)
from app.providers.azure.landing_zone.bundle import REPOSITORY_NAME, AzureLandingZoneBundle
from app.providers.azure.landing_zone.controls import azure_controls
from app.providers.azure.landing_zone.limits import (
    DefenderPlansCost,
    IdentityOnlyForDomainControllers,
    LocalEgressSkipsFirewall,
    ManagementGroupDepth,
    ManagementGroupIds,
    PairedGovernedRegions,
    PolicyAssignmentsPerScope,
    StrictResidencyAgainstPairs,
    SubscriptionCreationLimits,
    SubscriptionNames,
)


@cache
def azure_landing_zone() -> LandingZoneToolkit:
    """Management groups and vended subscriptions, Azure Policy and hub-and-spoke networking, applied as deployment
    stacks at the organization's management group (§22.12)."""
    from app.providers.azure.provider import REGION_PAIRS

    return LandingZoneToolkit(repository_name=REPOSITORY_NAME, bundle=AzureLandingZoneBundle(),
                              checks=(ManagementGroupDepth(), ManagementGroupIds(), SubscriptionNames(),
                                      PairedGovernedRegions(REGION_PAIRS), PolicyAssignmentsPerScope()),
                              advice=(DefenderPlansCost(), LocalEgressSkipsFirewall(), StrictResidencyAgainstPairs(),
                                      IdentityOnlyForDomainControllers(), SubscriptionCreationLimits()),
                              answers=AzureLandingZoneAnswers, namer=AzureSubscriptionNamer, controls=azure_controls(),
                              preview_answers=PREVIEW_ANSWERS, root_detail=root_detail, units=AZURE_UNITS)
