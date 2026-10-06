from app.providers.azure.landing_zone.stacks.base import (
    TENANT_SCHEMA,
    Stack,
    deployment_name,
    management_group_resource_id,
    nested,
)

ALIASES_API = "2021-10-01"
MANAGEMENT_GROUPS_API = "2023-04-01"
DEV_TEST_TIERS = ("nonprod", "sandbox")


class SubscriptionsStack(Stack):
    """Subscription aliases against the billing scope, each placed in its management group. Removing one from the
    design detaches it and never cancels it (MC5-5)."""

    name = "lz-subscriptions"
    description = "Subscriptions vended against the billing scope and placed in their management groups"
    unmanaged = "detachAll"
    needs_subscription_ids = False

    def resources(self, context):
        resources = []
        for account in context.accounts():
            ou = context.node_of(account)
            group = context.management_group(ou)
            workload = "DevTest" if context.tier_of(ou) in DEV_TEST_TIERS else "Production"
            resources.append({"type": "Microsoft.Subscription/aliases", "apiVersion": ALIASES_API, "name": account.name,
                              "scope": "/", "properties": {
                                  "displayName": account.name, "billingScope": context.answers.billing_scope,
                                  "workload": workload, "additionalProperties": {
                                      "managementGroupId": management_group_resource_id(group),
                                      "subscriptionTenantId": context.answers.tenant_id,
                                      "tags": {"org:managed-by": "cloudinfra"}}}})
            placement = {"type": "Microsoft.Management/managementGroups/subscriptions", "apiVersion": MANAGEMENT_GROUPS_API,
                         "name": f"[format('{{0}}/{{1}}', '{group}', parameters('subscriptionId'))]"}
            resolved = f"[reference(tenantResourceId('Microsoft.Subscription/aliases', '{account.name}'), '{ALIASES_API}')" \
                       ".subscriptionId]"
            resources.append(nested(deployment_name("place", account.name), TENANT_SCHEMA, [placement],
                                    {"subscriptionId": resolved}, [account.name], scope="/"))
        return resources
