import yaml

from app.landing_zone.cloudformation.base import FORMAT_VERSION, StackContext, StackRenderer
from app.synth.render import NoAliasDumper

GITHUB_OIDC_URL = "https://token.actions.githubusercontent.com"


def account_bootstrap_template() -> dict:
    """What every workload account needs before the platform can bootstrap projects in it."""
    return {
        "AWSTemplateFormatVersion": FORMAT_VERSION,
        "Description": "CloudInfra account bootstrap: GitHub OIDC provider and the platform provisioner role.",
        "Parameters": {"PlatformAccountId": {"Type": "String", "AllowedPattern": r"^\d{12}$"}},
        "Resources": {
            "GitHubOidcProvider": {"Type": "AWS::IAM::OIDCProvider", "Properties": {
                "Url": GITHUB_OIDC_URL, "ClientIdList": ["sts.amazonaws.com"]}},
            "ProvisionerRole": {"Type": "AWS::IAM::Role", "Properties": {
                "RoleName": "CloudInfraProvisioner",
                "AssumeRolePolicyDocument": {"Version": "2012-10-17", "Statement": [{
                    "Effect": "Allow", "Action": "sts:AssumeRole",
                    "Principal": {"AWS": {"Fn::Sub": "arn:${AWS::Partition}:iam::${PlatformAccountId}:root"}}}]},
                "Policies": [{"PolicyName": "ProjectBootstrap", "PolicyDocument": {"Version": "2012-10-17", "Statement": [
                    {"Sid": "ManageProjectRoles", "Effect": "Allow",
                     "Action": ["iam:CreateRole", "iam:DeleteRole", "iam:TagRole", "iam:UntagRole", "iam:GetRole",
                                "iam:PutRolePolicy", "iam:DeleteRolePolicy", "iam:AttachRolePolicy",
                                "iam:DetachRolePolicy", "iam:UpdateAssumeRolePolicy"],
                     "Resource": {"Fn::Sub": "arn:${AWS::Partition}:iam::${AWS::AccountId}:role/cloudinfra/*"}},
                    {"Sid": "ManageBootstrapStacks", "Effect": "Allow",
                     "Action": ["cloudformation:CreateStack", "cloudformation:UpdateStack", "cloudformation:DeleteStack",
                                "cloudformation:DescribeStacks"],
                     "Resource": {"Fn::Sub": "arn:${AWS::Partition}:cloudformation:*:${AWS::AccountId}:stack/cloudinfra-*/*"}},
                ]}}]}},
        },
    }


class BootstrapStack(StackRenderer):
    """Service-managed StackSet that installs the account bootstrap in every isolated OU's accounts, including new ones."""

    name = "lz-bootstrap"
    description = "Landing zone account bootstrap, auto-deployed to every account in the isolated OUs."

    def sections(self, context: StackContext) -> dict:
        answers = context.design.answers
        targets = [context.references.imported_id(ou) for ou in context.design.isolated_ous()]
        return {
            "Parameters": {"PlatformAccountId": {"Type": "String", "AllowedPattern": r"^\d{12}$"},
                           "SandboxOuId": {"Type": "String", "AllowedPattern": r"^ou-[0-9a-z]{4,32}-[a-z0-9]{8,32}$"}},
            "Resources": {"AccountBootstrap": {"Type": "AWS::CloudFormation::StackSet", "Properties": {
                "StackSetName": f"{answers.organization_name}-account-bootstrap",
                "PermissionModel": "SERVICE_MANAGED",
                "AutoDeployment": {"Enabled": True, "RetainStacksOnAccountRemoval": False},
                "Capabilities": ["CAPABILITY_NAMED_IAM"],
                "ManagedExecution": {"Active": True},
                "OperationPreferences": {"FailureTolerancePercentage": 10, "MaxConcurrentPercentage": 25},
                "Parameters": [{"ParameterKey": "PlatformAccountId", "ParameterValue": {"Ref": "PlatformAccountId"}}],
                "StackInstancesGroup": [{"DeploymentTargets": {"OrganizationalUnitIds": targets},
                                         "Regions": [answers.home_region]}],
                "TemplateBody": yaml.dump(account_bootstrap_template(), Dumper=NoAliasDumper, sort_keys=False)}}},
        }
