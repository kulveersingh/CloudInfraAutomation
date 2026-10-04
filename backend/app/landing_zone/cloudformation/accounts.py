from app.landing_zone.cloudformation.base import StackContext, StackRenderer, export
from app.landing_zone.cloudformation.references import OU_ID_PATTERN, pascal
from app.landing_zone.design import AccountPlan, OuNode
from app.landing_zone.designer import network_host_suffix

ACCOUNT_FACTORY = "AWS Control Tower Account Factory"
FOUNDATION_ACCOUNTS = ("log-archive", "audit")


class AccountsStack(StackRenderer):
    """Every other account, vended by Control Tower Account Factory straight into its OU, one at a time."""

    name = "lz-accounts"
    description = "Landing zone accounts vended through Control Tower Account Factory."

    def sections(self, context: StackContext) -> dict:
        organization = context.design.answers.organization_name
        host = network_host_suffix(context.design.answers)
        resources, outputs, previous = {}, {}, None
        for ou in context.design.walk():
            for account in ou.enabled_accounts():
                suffix = account.name.removeprefix(f"{organization}-")
                if suffix in FOUNDATION_ACCOUNTS:
                    continue
                key = f"Account{pascal(suffix)}"
                resources[key] = self._product(context, ou, account, previous)
                previous = key
                if suffix == host:
                    outputs["NetworkAccountId"] = export(context, "NetworkAccountId",
                                                         {"Fn::GetAtt": [key, "Outputs.AccountId"]})
        return {"Parameters": self._parameters(context), "Resources": resources, "Outputs": outputs}

    def _parameters(self, context: StackContext) -> dict:
        ou = {"Type": "String", "AllowedPattern": OU_ID_PATTERN}
        return {"SecurityOuId": ou, "SandboxOuId": ou,
                "AccountFactoryProductName": {"Type": "String", "Default": ACCOUNT_FACTORY},
                "AccountFactoryVersion": {"Type": "String", "Default": ACCOUNT_FACTORY},
                "SsoUserEmail": {"Type": "String", "Default": context.design.answers.management_email}}

    def _product(self, context: StackContext, ou: OuNode, account: AccountPlan, previous: str | None) -> dict:
        body = {"Type": "AWS::ServiceCatalog::CloudFormationProvisionedProduct",
                "DeletionPolicy": "Retain", "UpdateReplacePolicy": "Retain",
                "Properties": {
                    "ProductName": {"Ref": "AccountFactoryProductName"},
                    "ProvisioningArtifactName": {"Ref": "AccountFactoryVersion"},
                    "ProvisionedProductName": account.name,
                    "ProvisioningParameters": [
                        {"Key": "AccountName", "Value": account.name},
                        {"Key": "AccountEmail", "Value": account.email},
                        {"Key": "ManagedOrganizationalUnit", "Value": self._managed_ou(context, ou)},
                        {"Key": "SSOUserEmail", "Value": {"Ref": "SsoUserEmail"}},
                        {"Key": "SSOUserFirstName", "Value": "Platform"},
                        {"Key": "SSOUserLastName", "Value": "Admin"}]}}
        return {**body, "DependsOn": [previous]} if previous else body

    def _managed_ou(self, context: StackContext, ou: OuNode) -> dict:
        if ou.created_by_control_tower:
            return {"Fn::Sub": f"{ou.name} (${{{context.references.name_in_template(ou)}}})"}
        return {"Fn::Sub": [f"{ou.name} (${{OuId}})", {"OuId": context.references.imported_id(ou)}]}
