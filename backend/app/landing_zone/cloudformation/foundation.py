from app.landing_zone.cloudformation.base import StackContext, StackRenderer, export
from app.landing_zone.designer import AccountNamer

LANDING_ZONE_VERSION = "3.3"
ACCESS_LOG_RETENTION_DAYS = 3650
RETAIN = {"DeletionPolicy": "Retain", "UpdateReplacePolicy": "Retain"}


def _trust(service: str) -> dict:
    return {"Version": "2012-10-17", "Statement": [
        {"Effect": "Allow", "Principal": {"Service": service}, "Action": "sts:AssumeRole"}]}


def _inline(name: str, actions: list[str], resource) -> list[dict]:
    return [{"PolicyName": name, "PolicyDocument": {"Version": "2012-10-17", "Statement": [
        {"Effect": "Allow", "Action": actions, "Resource": resource}]}}]


CONTROL_TOWER_ROLES = {
    "ControlTowerAdminRole": {
        "RoleName": "AWSControlTowerAdmin", "Path": "/service-role/",
        "AssumeRolePolicyDocument": _trust("controltower.amazonaws.com"),
        "ManagedPolicyArns": [{"Fn::Sub": "arn:${AWS::Partition}:iam::aws:policy/service-role/AWSControlTowerServiceRolePolicy"}],
        "Policies": _inline("AWSControlTowerAdminPolicy", ["ec2:DescribeAvailabilityZones"], "*")},
    "ControlTowerCloudTrailRole": {
        "RoleName": "AWSControlTowerCloudTrailRole", "Path": "/service-role/",
        "AssumeRolePolicyDocument": _trust("cloudtrail.amazonaws.com"),
        "Policies": _inline("AWSControlTowerCloudTrailRolePolicy", ["logs:CreateLogStream", "logs:PutLogEvents"],
                            {"Fn::Sub": "arn:${AWS::Partition}:logs:*:*:log-group:aws-controltower/CloudTrailLogs:*"})},
    "ControlTowerStackSetRole": {
        "RoleName": "AWSControlTowerStackSetRole", "Path": "/service-role/",
        "AssumeRolePolicyDocument": _trust("cloudformation.amazonaws.com"),
        "Policies": _inline("AWSControlTowerStackSetRolePolicy", ["sts:AssumeRole"],
                            {"Fn::Sub": "arn:${AWS::Partition}:iam::*:role/AWSControlTowerExecution"})},
    "ControlTowerConfigAggregatorRole": {
        "RoleName": "AWSControlTowerConfigAggregatorRoleForOrganizations", "Path": "/service-role/",
        "AssumeRolePolicyDocument": _trust("config.amazonaws.com"),
        "ManagedPolicyArns": [{"Fn::Sub": "arn:${AWS::Partition}:iam::aws:policy/service-role/AWSConfigRoleForOrganizations"}]},
}


class FoundationStack(StackRenderer):
    """The organization, Control Tower prerequisites, Log Archive and Audit accounts, and the landing zone."""

    name = "lz-foundation"
    description = "Landing zone foundation: AWS Organization, Control Tower roles, security accounts, landing zone."

    def sections(self, context: StackContext) -> dict:
        answers = context.design.answers
        namer = AccountNamer(answers)
        resources = {"Organization": {"Type": "AWS::Organizations::Organization", **RETAIN,
                                      "Properties": {"FeatureSet": "ALL"}}}
        resources |= {key: {"Type": "AWS::IAM::Role", "Properties": body} for key, body in CONTROL_TOWER_ROLES.items()}
        for key, suffix in (("LogArchiveAccount", "log-archive"), ("AuditAccount", "audit")):
            account = namer.account(suffix)
            resources[key] = {"Type": "AWS::Organizations::Account", **RETAIN, "DependsOn": ["Organization"],
                              "Properties": {"AccountName": account.name, "Email": account.email}}
        resources["LandingZone"] = {"Type": "AWS::ControlTower::LandingZone", **RETAIN,
                                    "DependsOn": ["Organization", *CONTROL_TOWER_ROLES],
                                    "Properties": {"Version": {"Ref": "LandingZoneVersion"},
                                                   "Manifest": self._manifest(context)}}
        return {
            "Parameters": {"LandingZoneVersion": {"Type": "String", "Default": LANDING_ZONE_VERSION,
                                                  "AllowedPattern": r"^\d+\.\d+$"}},
            "Resources": resources,
            "Outputs": {
                "OrganizationId": export(context, "OrganizationId", {"Fn::GetAtt": ["Organization", "Id"]}),
                "RootId": export(context, "RootId", {"Fn::GetAtt": ["Organization", "RootId"]}),
                "LogArchiveAccountId": {"Value": {"Fn::GetAtt": ["LogArchiveAccount", "AccountId"]}},
                "AuditAccountId": {"Value": {"Fn::GetAtt": ["AuditAccount", "AccountId"]}},
            },
        }

    def _manifest(self, context: StackContext) -> dict:
        answers = context.design.answers
        sandbox = next(ou for ou in context.design.environment_ous() if ou.tier == "sandbox")
        return {
            "governedRegions": answers.governed_regions,
            "organizationStructure": {"security": {"name": "Security"}, "sandbox": {"name": sandbox.name}},
            "centralizedLogging": {
                "accountId": {"Fn::GetAtt": ["LogArchiveAccount", "AccountId"]},
                "configurations": {"loggingBucket": {"retentionDays": answers.log_retention_days},
                                   "accessLoggingBucket": {"retentionDays": ACCESS_LOG_RETENTION_DAYS}},
                "enabled": True},
            "securityRoles": {"accountId": {"Fn::GetAtt": ["AuditAccount", "AccountId"]}},
            "accessManagement": {"enabled": True},
        }
