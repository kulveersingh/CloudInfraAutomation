from functools import cache

from app.landing_zone.readback import REPOSITORY_NAME
from app.landing_zone.toolkit import LandingZoneToolkit
from app.providers.aws.landing_zone.cloudformation.bundle import LandingZoneBundle, StackSizeRule
from app.providers.aws.landing_zone.limits import MaximumDepth, OuSizeWithinRegistrationLimit, ScpQuotaCheck


@cache
def aws_landing_zone() -> LandingZoneToolkit:
    """Organizations, Control Tower and CloudFormation stacks (§20)."""
    return LandingZoneToolkit(repository_name=REPOSITORY_NAME, bundle=LandingZoneBundle.default(),
                              checks=(MaximumDepth(), ScpQuotaCheck(), StackSizeRule()),
                              advice=(OuSizeWithinRegistrationLimit(),))
