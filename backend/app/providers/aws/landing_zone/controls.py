CONTROL_ARN = "arn:aws:controlcatalog:::control/{}"


def control_identifier(control_id: str) -> str:
    """The global identifier Control Tower requires; regional AWS-GR_ identifiers are no longer supported."""
    return CONTROL_ARN.format(control_id)
