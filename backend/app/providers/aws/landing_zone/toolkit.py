from functools import cache

from app.landing_zone.readback import REPOSITORY_NAME
from app.landing_zone.toolkit import LandingZoneToolkit
from app.providers.aws.landing_zone.answers import (
    AWS_UNITS,
    PREVIEW_ANSWERS,
    AwsAccountNamer,
    AwsLandingZoneAnswers,
    root_detail,
)
from app.providers.aws.landing_zone.cloudformation.bundle import LandingZoneBundle, StackSizeRule
from app.providers.aws.landing_zone.controls import aws_controls
from app.providers.aws.landing_zone.limits import (
    MaximumDepth,
    OuSizeWithinRegistrationLimit,
    ScpQuotaCheck,
    StrictResidencyBlocksReplication,
)


@cache
def aws_landing_zone() -> LandingZoneToolkit:
    """Organizations, Control Tower and CloudFormation stacks (§20)."""
    return LandingZoneToolkit(repository_name=REPOSITORY_NAME, bundle=LandingZoneBundle.default(),
                              checks=(MaximumDepth(), ScpQuotaCheck(), StackSizeRule()),
                              advice=(StrictResidencyBlocksReplication(), OuSizeWithinRegistrationLimit()),
                              answers=AwsLandingZoneAnswers, namer=AwsAccountNamer, controls=aws_controls(),
                              preview_answers=PREVIEW_ANSWERS, root_detail=root_detail, units=AWS_UNITS)
