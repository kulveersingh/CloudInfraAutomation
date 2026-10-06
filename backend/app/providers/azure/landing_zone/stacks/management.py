from app.providers.azure.landing_zone.stacks.base import (
    LOCATION,
    SUBSCRIPTION_SCHEMA,
    Stack,
    StackContext,
    deployment_name,
    in_resource_group,
    nested,
)
from app.providers.azure.landing_zone.stacks.storage import locked_account

WORKSPACES_API = "2023-09-01"
DIAGNOSTICS_API = "2021-05-01-preview"
PRICINGS_API = "2024-01-01"
SENTINEL_API = "2024-03-01"
MAX_WORKSPACE_RETENTION = 730
ACTIVITY_CATEGORIES = ["Administrative", "Security", "ServiceHealth", "Alert", "Recommendation", "Policy", "Autoscale",
                       "ResourceHealth"]
DEFENDER_PLANS = ["CloudPosture", "VirtualMachines", "StorageAccounts", "SqlServers", "CosmosDbs"]
LOGS = {"cloudinfra-role": "logs"}


class ManagementStack(Stack):
    """The central Log Analytics workspace and locked log account, every subscription's Activity Log sent there,
    Defender plans when chosen, and Sentinel with Security Tooling."""

    name = "lz-management"
    description = "Central logs, Activity Log from every subscription, Defender plans and Sentinel"

    def resources(self, context):
        management, organization = context.security_unit(0), context.organization
        retention = context.design.answers.log_retention_days
        central = [{"type": "Microsoft.OperationalInsights/workspaces", "apiVersion": WORKSPACES_API,
                    "name": f"law-{organization}", "location": context.home, "tags": LOGS,
                    "properties": {"sku": {"name": "PerGB2018"},
                                   "retentionInDays": min(retention, MAX_WORKSPACE_RETENTION)}},
                   *locked_account("[concat('stlogs', uniqueString(subscription().id))]", context.home, retention,
                                   tags=LOGS)]
        resources = [in_resource_group("management", context.subscription(management), "rg-management", LOCATION, central)]
        workspace = (f"[format('/subscriptions/{{0}}/resourceGroups/rg-management/providers/"
                     f"Microsoft.OperationalInsights/workspaces/law-{organization}', "
                     f"parameters('subscriptionIds')['{management}'])]")
        resources += [self._subscription(context, account.name, workspace) for account in context.accounts()]
        if context.design.answers.security_tooling:
            resources.append(self._sentinel(context))
        return resources

    @staticmethod
    def _subscription(context: StackContext, name: str, workspace: str) -> dict:
        settings = {"type": "Microsoft.Insights/diagnosticSettings", "apiVersion": DIAGNOSTICS_API,
                    "name": "to-central-workspace", "properties": {
                        "workspaceId": "[parameters('workspaceId')]",
                        "logs": [{"category": category, "enabled": True} for category in ACTIVITY_CATEGORIES]}}
        plans = [{"type": "Microsoft.Security/pricings", "apiVersion": PRICINGS_API, "name": plan,
                  "properties": {"pricingTier": "Standard"}} for plan in DEFENDER_PLANS
                 if context.answers.defender == "standard"]
        return nested(deployment_name("subscription", name), SUBSCRIPTION_SCHEMA, [settings, *plans],
                      {"workspaceId": workspace}, ["management"], subscriptionId=context.subscription(name))

    @staticmethod
    def _sentinel(context: StackContext) -> dict:
        tooling = context.design.namer.unit(context.design.units.security_tooling).name
        workspace = f"law-{context.organization}-sentinel"
        resources = [{"type": "Microsoft.OperationalInsights/workspaces", "apiVersion": WORKSPACES_API, "name": workspace,
                      "location": context.home, "properties": {"sku": {"name": "PerGB2018"}}},
                     {"type": "Microsoft.SecurityInsights/onboardingStates", "apiVersion": SENTINEL_API, "name": "default",
                      "scope": f"[format('Microsoft.OperationalInsights/workspaces/{{0}}', '{workspace}')]",
                      "dependsOn": [workspace], "properties": {}}]
        return in_resource_group("sentinel", context.subscription(tooling), "rg-sentinel", LOCATION, resources)
