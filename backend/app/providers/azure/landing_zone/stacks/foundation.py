from app.providers.azure.landing_zone.controls import azure_controls
from app.providers.azure.landing_zone.custom_policies import DEFINITIONS
from app.providers.azure.landing_zone.stacks.base import Stack, escaped, management_group_resource_id

MANAGEMENT_GROUPS_API = "2023-04-01"
POLICY_API = "2023-04-01"


class FoundationStack(Stack):
    """The management groups below the organization's own, and the platform's custom policy definitions."""

    name = "lz-foundation"
    description = "Management groups and the platform's custom policy definitions"
    needs_subscription_ids = False

    def resources(self, context):
        groups = []
        for ou in context.design.walk():
            parent = context.parent(ou)
            group = {"type": "Microsoft.Management/managementGroups", "apiVersion": MANAGEMENT_GROUPS_API,
                     "name": context.management_group(ou), "scope": "/", "properties": {
                         "displayName": ou.name,
                         "details": {"parent": {"id": management_group_resource_id(context.management_group(parent))}}}}
            groups.append({**group, **({"dependsOn": [context.management_group(parent)]} if parent else {})})
        snapshot = azure_controls().snapshot
        definitions = [{"type": "Microsoft.Authorization/policyDefinitions", "apiVersion": POLICY_API, "name": control_id,
                        "properties": {"policyType": "Custom", "mode": body["mode"],
                                       "displayName": snapshot.get(control_id).name,
                                       "metadata": {"category": "CloudInfra"}, "parameters": body.get("parameters", {}),
                                       "policyRule": escaped(body["policyRule"])}}
                       for control_id, body in DEFINITIONS.items()]
        return groups + definitions
