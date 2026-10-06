import hashlib

from app.landing_zone.catalog.resolver import EnabledControl
from app.providers.azure.landing_zone.controls import azure_assignments
from app.providers.azure.landing_zone.stacks.base import (
    MANAGEMENT_GROUP_SCHEMA,
    ROLES_API,
    SUBSCRIPTION_SCHEMA,
    Stack,
    StackContext,
    deployment_name,
    management_group_resource_id,
    nested,
    role_definition,
)

POLICY_API = "2023-04-01"
BUDGETS_API = "2023-11-01"
READER = "acdd72a7-3385-48ef-bd42-f606fba81ae7"
SECURITY_ADMIN = "fb1c8493-542b-48eb-b624-b4c8fea62acd"
NETWORK_CONTRIBUTOR = "4d97b98b-1d4f-4787-a291-c67834d212e7"
NO_HUB = "00000000-0000-0000-0000-000000000000"  # with no hub, every peering is outside it
BUDGET_ALERT_PERCENT = 80
# Values the platform's own definitions need from the landing zone, as parameters of each assignment.
CONTEXT_PARAMETERS = {"cloudinfra-deny-peering-outside-hub": "hubSubscriptionId"}


def assignment_name(group: str, control_id: str) -> str:
    """Assignment names at management-group scope are at most 24 characters."""
    return f"ci-{hashlib.sha1(f'{group}:{control_id}'.encode()).hexdigest()[:12]}"


def definition_id(organization: str, control_id: str) -> str:
    if control_id.startswith("cloudinfra-"):
        return f"{management_group_resource_id(organization)}/providers/Microsoft.Authorization/policyDefinitions/{control_id}"
    return f"/providers/Microsoft.Authorization/policyDefinitions/{control_id}"


def role(name: str, role_id: str, principal: str) -> dict:
    return {"type": "Microsoft.Authorization/roleAssignments", "apiVersion": ROLES_API, "name": f"[guid('{name}')]",
            "properties": {"roleDefinitionId": role_definition(role_id), "principalId": principal,
                           "principalType": "Group"}}


class StructureStack(Stack):
    """Policy assignments on each management group (Policy Staging evaluates without enforcing), the admin groups'
    roles, and the sandbox budgets."""

    name = "lz-structure"
    description = "Policy assignments, admin group roles and sandbox budgets"

    def resources(self, context):
        return [*self._policies(context), *self._roles(context), *self._budgets(context)]

    def _policies(self, context: StackContext) -> list[dict]:
        everything = {enabled.control.id: enabled for controls in context.controls.values() for enabled in controls}
        deployments = []
        for ou in context.design.walk():
            staging = ou.kind == "policy_staging"
            enabled = list(everything.values()) if staging else context.controls.get(ou.key, [])
            if not enabled:
                continue
            group = context.management_group(ou)
            assignments = [self._assignment(context, group, item, staging) for item in enabled]
            needed = {CONTEXT_PARAMETERS[item.control.id] for item in enabled if item.control.id in CONTEXT_PARAMETERS}
            parameters = {name: self._context_value(context, name) for name in sorted(needed)}
            deployments.append(nested(deployment_name("policy", group), MANAGEMENT_GROUP_SCHEMA, assignments, parameters,
                                      scope=f"Microsoft.Management/managementGroups/{group}"))
        return deployments

    @staticmethod
    def _assignment(context: StackContext, group: str, enabled: EnabledControl, staging: bool) -> dict:
        control = enabled.control
        parameters = azure_assignments()[control.id].parameters(enabled.parameters)
        if control.id in CONTEXT_PARAMETERS:
            name = CONTEXT_PARAMETERS[control.id]
            parameters[name] = {"value": f"[parameters('{name}')]"}
        return {"type": "Microsoft.Authorization/policyAssignments", "apiVersion": POLICY_API,
                "name": assignment_name(group, control.id), "properties": {
                    "displayName": control.name[:128], "policyDefinitionId": definition_id(context.organization, control.id),
                    "enforcementMode": "DoNotEnforce" if staging else "Default", "parameters": parameters}}

    @staticmethod
    def _context_value(context: StackContext, name: str) -> str:
        hub = context.hub_subscription()
        return context.subscription(hub) if hub else NO_HUB

    def _roles(self, context: StackContext) -> list[dict]:
        groups, organization = context.answers.groups, context.organization
        roles = [role(f"{organization}-platform-admins", READER, groups.platform_admins),
                 role(f"{organization}-security-admins", SECURITY_ADMIN, groups.security_admins)]
        network = role(f"{organization}-network-admins", NETWORK_CONTRIBUTOR, groups.network_admins)
        group = context.management_group(next(ou for ou in context.design.walk() if ou.kind == "infrastructure"))
        return [*roles, nested(deployment_name("roles", group), MANAGEMENT_GROUP_SCHEMA, [network],
                               scope=f"Microsoft.Management/managementGroups/{group}")]

    @staticmethod
    def _budgets(context: StackContext) -> list[dict]:
        budgets = []
        sandbox = context.design.answers.sandbox
        for account in context.sandbox_accounts():
            budget = {"type": "Microsoft.Consumption/budgets", "apiVersion": BUDGETS_API, "name": "sandbox-monthly",
                      "properties": {"category": "Cost", "amount": sandbox.monthly_budget_usd, "timeGrain": "Monthly",
                                     "timePeriod": {"startDate": "[parameters('startDate')]"}, "notifications": {
                                         "actual80": {"enabled": True, "operator": "GreaterThan",
                                                      "threshold": BUDGET_ALERT_PERCENT, "thresholdType": "Actual",
                                                      "contactRoles": ["Owner"]}}}}
            deployment = nested(deployment_name("budget", account.name), SUBSCRIPTION_SCHEMA, [budget],
                                subscriptionId=context.subscription(account.name))
            deployment["properties"]["template"]["parameters"]["startDate"] = {
                "type": "string", "defaultValue": "[utcNow('yyyy-MM-01')]"}
            budgets.append(deployment)
        return budgets
