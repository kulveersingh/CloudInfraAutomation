"""The Azure landing-zone repository (§22.12.5, MC-5b): ARM templates applied as deployment stacks at the
organization's management group, their parameters, the one-time seed script, the workflow and the README."""

import ipaddress
import json
import re

import pytest

from app.landing_zone.catalog.templates import TemplateRegistry
from app.providers.azure.expressions import unique_string
from tests.lz_factories import CATALOG, add_ou
from tests.test_azure_landing_zone import EA_SCOPE, GROUPS, MCA_SCOPE, TENANT, design

STACKS = ["lz-foundation", "lz-subscriptions", "lz-structure", "lz-management", "lz-network", "lz-vault"]
TEMPLATES = [template.id for template in TemplateRegistry.default().all()]
MANAGEMENT_GROUP_SCHEMA = "https://schema.management.azure.com/schemas/2019-08-01/managementGroupDeploymentTemplate.json#"
SHARED_KEYS = "8c6a50c6-9ffd-4ae7-986f-5fa6111f9a54"
NIC_PUBLIC_IPS = "83a86a26-fd1f-447c-b59d-e51f44264114"  # its Deny is fixed: no effect parameter
ALLOWED_LOCATIONS = "e56962a6-4747-49cd-b67b-bf8b01975c4c"
KEY_ROTATION = "d8cf8476-a2ec-4916-896e-992351803c44"
NETWORK_CONTRIBUTOR = "4d97b98b-1d4f-4787-a291-c67834d212e7"


def files(edits=(), **overrides) -> dict[str, str]:
    from app.providers.azure.provider import AzureProvider

    return AzureProvider().landing_zone().bundle.render(design(edits, **overrides), CATALOG)


def stack(name: str, edits=(), **overrides) -> dict:
    return json.loads(files(edits, **overrides)[f"stacks/{name}/main.json"])


def flatten(template: dict) -> list[dict]:
    """Every resource, including those inside nested deployments."""
    found = []
    for resource in template["resources"]:
        found.append(resource)
        if resource["type"] == "Microsoft.Resources/deployments":
            found += flatten(resource["properties"]["template"])
    return found


def of_type(template: dict, type_name: str) -> list[dict]:
    return [resource for resource in flatten(template) if resource["type"] == type_name]


def named(template: dict, type_name: str, name: str) -> dict:
    [found] = [resource for resource in of_type(template, type_name) if resource["name"] == name]
    return found


def templates(template: dict) -> list[dict]:
    """The template and every nested deployment's template."""
    return [template, *[nested for resource in template["resources"] if resource["type"] == "Microsoft.Resources/deployments"
                        for nested in templates(resource["properties"]["template"])]]


def text(template: dict) -> str:
    return json.dumps(template)


# ---- the repository ----

def test_the_repository_holds_every_stack_and_its_tooling():
    expected = {f"stacks/{name}/{file}" for name in STACKS for file in ("main.json", "parameters.json")}
    assert expected | {"scripts/bootstrap-seed.sh", ".github/workflows/apply.yml", "README.md", "design.json",
                       "docs/controls.md", "docs/ou-structure.svg"} <= set(files())


def test_every_stack_is_a_management_group_template_deployed_from_the_home_region():
    rendered = files()
    parameters = json.loads(rendered["stacks/lz-network/parameters.json"])
    assert ({json.loads(rendered[f"stacks/{name}/main.json"])["$schema"] for name in STACKS},
            parameters["parameters"]["location"]) == ({MANAGEMENT_GROUP_SCHEMA}, {"value": "eastus2"})


@pytest.mark.parametrize("template", TEMPLATES)
def test_every_templates_stacks_pass_the_lint_and_schema_rules(template):
    from app.providers.azure.landing_zone.stacks.lint import landing_zone_linter

    chosen = TemplateRegistry.default().get(template)
    rendered = files(chosen.edits, **chosen.answers_for("azure"))
    findings = {name: landing_zone_linter().lint(json.loads(rendered[f"stacks/{name}/main.json"])) for name in STACKS}
    assert {name: found for name, found in findings.items() if found} == {}


def test_the_lint_rules_find_broad_roles_open_storage_and_unknown_types():
    from app.providers.azure.landing_zone.stacks.lint import landing_zone_linter

    bad = {"resources": [
        {"type": "Microsoft.Authorization/roleAssignments", "apiVersion": "2022-04-01", "name": "owner",
         "properties": {"roleDefinitionId": "/providers/Microsoft.Authorization/roleDefinitions/"
                                            "8e3af657-a8ff-443c-a75c-2fe8c4bcb635", "principalId": "p"}},
        {"type": "Microsoft.Resources/deployments", "apiVersion": "2024-03-01", "name": "inner",
         "properties": {"mode": "Incremental", "template": {"resources": [
             {"type": "Microsoft.Nothing/things", "apiVersion": "2020-01-01", "name": "x"}]}}}]}
    assert landing_zone_linter().lint(bad) == [
        "Microsoft.Authorization/roleAssignments owner: broad role Owner.",
        "Microsoft.Nothing/things x: unknown resource type."]


@pytest.mark.parametrize("name", STACKS)
def test_every_template_depends_only_on_what_it_defines_and_declares_what_it_uses(name):
    everything = stack(name, network={"flows": [{"source": "dev", "destination": "stage", "port": 443,
                                                 "reason": "Payments API"}], "on_premises": "vpn"})
    for template in templates(everything):
        defined = {resource["name"] for resource in template["resources"]}
        used = set(re.findall(r"parameters\('(\w+)'\)", json.dumps(
            {key: value for key, value in template.items() if key != "resources"} | {"resources": [
                {key: value for key, value in resource.items() if key != "properties"}
                | ({"properties": {k: v for k, v in resource["properties"].items() if k != "template"}}
                   if "properties" in resource else {}) for resource in template["resources"]]})))
        assert ([entry for resource in template["resources"] for entry in resource.get("dependsOn", [])
                 if entry not in defined], used - set(template.get("parameters", {}))) == ([], set())


# ---- lz-foundation ----

def test_management_groups_nest_under_their_parents_below_the_organizations_own():
    document = stack("lz-foundation", [add_ou("Payments")])
    prod = named(document, "Microsoft.Management/managementGroups", "acme-prod")
    payments = named(document, "Microsoft.Management/managementGroups", "acme-custom-payments")
    assert (prod["scope"], prod["properties"]["displayName"], prod["properties"]["details"]["parent"]["id"],
            payments["properties"]["details"]["parent"]["id"], payments["dependsOn"]) == (
        "/", "PROD", "/providers/Microsoft.Management/managementGroups/acme",
        "/providers/Microsoft.Management/managementGroups/acme-prod", ["acme-prod"])


def test_the_platforms_own_policy_definitions_are_defined_once_at_the_organization():
    definitions = of_type(stack("lz-foundation"), "Microsoft.Authorization/policyDefinitions")
    deny = next(item for item in definitions if item["name"] == "cloudinfra-deny-delete-data-stores")
    assert ({item["properties"]["policyType"] for item in definitions}, len(definitions) == len({
        item["name"] for item in definitions}), deny["properties"]["policyRule"]["then"]) == (
        {"Custom"}, True, {"effect": "denyAction", "details": {"actionNames": ["delete"]}})


# ---- lz-subscriptions ----

def test_every_enabled_unit_is_a_subscription_alias_against_the_billing_scope():
    aliases = {item["name"]: item for item in of_type(stack("lz-subscriptions"), "Microsoft.Subscription/aliases")}
    prod, dev = aliases["acme-payments-prod"]["properties"], aliases["acme-payments-dev"]["properties"]
    assert (aliases["acme-payments-prod"]["scope"], prod["billingScope"], prod["workload"], dev["workload"],
            prod["displayName"], prod["additionalProperties"]["managementGroupId"],
            prod["additionalProperties"]["subscriptionTenantId"]) == (
        "/", EA_SCOPE, "Production", "DevTest", "acme-payments-prod",
        "/providers/Microsoft.Management/managementGroups/acme-prod", TENANT)


def test_subscriptions_are_placed_in_their_management_group_by_id_once_created():
    placement = named(stack("lz-subscriptions"), "Microsoft.Resources/deployments", "place-acme-payments-prod")
    [moved] = placement["properties"]["template"]["resources"]
    assert (placement["scope"], placement["properties"]["parameters"]["subscriptionId"]["value"], moved["name"]) == (
        "/", ("[reference(tenantResourceId('Microsoft.Subscription/aliases', 'acme-payments-prod'), '2021-10-01')"
              ".subscriptionId]"), "[format('{0}/{1}', 'acme-prod', parameters('subscriptionId'))]")


def test_disabled_units_are_not_created():
    document = stack("lz-subscriptions", [{"op": "disable_account", "account": "acme-payments-dev"}])
    assert "acme-payments-dev" not in {item["name"] for item in of_type(document, "Microsoft.Subscription/aliases")}


# ---- lz-structure ----

def assignments(document: dict, management_group: str) -> list[dict]:
    nested = named(document, "Microsoft.Resources/deployments", f"policy-{management_group}")
    return [item for item in nested["properties"]["template"]["resources"]
            if item["type"] == "Microsoft.Authorization/policyAssignments"]


def assigned(document: dict, management_group: str, definition: str) -> dict:
    [found] = [item for item in assignments(document, management_group)
               if item["properties"]["policyDefinitionId"].endswith(f"/{definition}")]
    return found


def test_controls_are_assigned_on_the_top_most_management_group_with_their_effect():
    document = stack("lz-structure", [add_ou("Payments")])
    shared_keys = assigned(document, "acme-prod", SHARED_KEYS)
    nested = named(document, "Microsoft.Resources/deployments", "policy-acme-prod")
    assert (nested["scope"], shared_keys["properties"]["policyDefinitionId"], shared_keys["properties"]["parameters"],
            shared_keys["properties"]["enforcementMode"], "policy-acme-custom-payments" in {
                item["name"] for item in of_type(document, "Microsoft.Resources/deployments")}) == (
        "Microsoft.Management/managementGroups/acme-prod",
        f"/providers/Microsoft.Authorization/policyDefinitions/{SHARED_KEYS}", {"effect": {"value": "Deny"}},
        "Default", False)


def test_a_definition_with_a_fixed_effect_gets_no_effect_parameter():
    assert assigned(stack("lz-structure"), "acme-prod", NIC_PUBLIC_IPS)["properties"]["parameters"] == {}


def test_assignment_names_fit_twenty_four_characters_and_stay_unique():
    names = [item["name"] for item in assignments(stack("lz-structure"), "acme-prod")]
    assert (max(map(len, names)) <= 24, len(names) == len(set(names))) == (True, True)


def test_allowed_locations_are_the_governed_regions():
    document = stack("lz-structure", control_packs=["data-residency"])
    assert assigned(document, "acme-prod", ALLOWED_LOCATIONS)["properties"]["parameters"] == {
        "effect": {"value": "Deny"}, "listOfAllowedLocations": {"value": ["eastus2", "centralus"]}}


def test_keys_must_rotate_within_ninety_days():
    document = stack("lz-structure", control_packs=["foundation", "key-management"])
    assert assigned(document, "acme-prod", KEY_ROTATION)["properties"]["parameters"]["maximumDaysToRotate"] == {
        "value": 90}


def test_the_platforms_own_definitions_are_found_at_the_organization():
    document = stack("lz-structure", control_packs=["foundation", "network-hardening"])
    peering = assigned(document, "acme-prod", "cloudinfra-deny-peering-outside-hub")["properties"]
    assert (peering["policyDefinitionId"], peering["parameters"]["hubSubscriptionId"]) == (
        ("/providers/Microsoft.Management/managementGroups/acme/providers/Microsoft.Authorization/policyDefinitions/"
         "cloudinfra-deny-peering-outside-hub"), {"value": "[parameters('subscriptionIds')['acme-connectivity']]"})


def test_policy_staging_evaluates_every_control_without_enforcing():
    document = stack("lz-structure")
    staged = assignments(document, "acme-policy-staging")
    enforced = {item["properties"]["policyDefinitionId"] for item in of_type(
        document, "Microsoft.Authorization/policyAssignments") if item["properties"]["enforcementMode"] == "Default"}
    assert ({item["properties"]["enforcementMode"] for item in staged},
            {item["properties"]["policyDefinitionId"] for item in staged} >= enforced) == ({"DoNotEnforce"}, True)


def test_admin_groups_get_narrow_roles():
    roles = {item["properties"]["principalId"]: item["properties"]["roleDefinitionId"].rsplit("/", 1)[1]
             for item in of_type(stack("lz-structure"), "Microsoft.Authorization/roleAssignments")}
    assert (roles[GROUPS["platform_admins"]], roles[GROUPS["security_admins"]], roles[GROUPS["network_admins"]]) == (
        "acdd72a7-3385-48ef-bd42-f606fba81ae7", "fb1c8493-542b-48eb-b624-b4c8fea62acd", NETWORK_CONTRIBUTOR)


def test_sandbox_subscriptions_get_their_budget():
    budget = of_type(stack("lz-structure"), "Microsoft.Consumption/budgets")[0]
    assert (budget["properties"]["amount"], budget["properties"]["timeGrain"]) == (500, "Monthly")


# ---- lz-management ----

def test_logs_go_to_a_central_workspace_and_a_locked_account():
    document = stack("lz-management")
    workspace = of_type(document, "Microsoft.OperationalInsights/workspaces")[0]
    [account] = of_type(document, "Microsoft.Storage/storageAccounts")
    policy = account["properties"]["immutableStorageWithVersioning"]["immutabilityPolicy"]
    assert (workspace["properties"]["retentionInDays"], workspace["tags"], policy["state"],
            policy["immutabilityPeriodSinceCreationInDays"]) == (365, {"cloudinfra-role": "logs"}, "Locked", 365)


def test_every_subscription_sends_its_activity_log_to_the_workspace():
    document = stack("lz-management")
    settings = of_type(document, "Microsoft.Insights/diagnosticSettings")
    assert len(settings) == len(of_type(stack("lz-subscriptions"), "Microsoft.Subscription/aliases"))


def test_defender_plans_only_on_standard():
    foundational = of_type(stack("lz-management"), "Microsoft.Security/pricings")
    standard = of_type(stack("lz-management", provider_answers={"defender": "standard"}), "Microsoft.Security/pricings")
    assert (foundational, {item["properties"]["pricingTier"] for item in standard}) == ([], {"Standard"})


def test_sentinel_only_with_security_tooling():
    with_tooling = of_type(stack("lz-management"), "Microsoft.SecurityInsights/onboardingStates")
    without = of_type(stack("lz-management", security_tooling=False), "Microsoft.SecurityInsights/onboardingStates")
    assert (len(with_tooling), without) == (1, [])


# ---- lz-network ----

def hub_subnets(document: dict, region: str) -> dict[str, str]:
    hub = named(document, "Microsoft.Network/virtualNetworks", f"vnet-hub-{region}")
    return {subnet["name"]: subnet["properties"]["addressPrefix"] for subnet in hub["properties"]["subnets"]}


def test_each_governed_region_has_a_hub_with_a_firewall():
    document = stack("lz-network")
    firewalls = of_type(document, "Microsoft.Network/azureFirewalls")
    assert ([item["name"] for item in firewalls], {item["properties"]["sku"]["tier"] for item in firewalls},
            set(hub_subnets(document, "eastus2"))) == (
        ["afw-eastus2", "afw-centralus"], {"Standard"}, {"AzureFirewallSubnet"})


def test_premium_firewalls_inspect_with_idps():
    document = stack("lz-network", provider_answers={"firewall_tier": "premium"})
    policy = of_type(document, "Microsoft.Network/firewallPolicies")[0]["properties"]
    assert (policy["sku"]["tier"], policy["intrusionDetection"]["mode"]) == ("Premium", "Deny")


def test_each_workload_subscription_has_a_spoke_per_region_routed_through_the_firewall():
    document = stack("lz-network")
    spoke = next(item for item in of_type(document, "Microsoft.Network/virtualNetworks") if item["name"] == "vnet-eastus2")
    subnets = {subnet["name"]: subnet["properties"] for subnet in spoke["properties"]["subnets"]}
    firewall_ip = str(ipaddress.ip_network(hub_subnets(document, "eastus2")["AzureFirewallSubnet"])[4])
    route = of_type(document, "Microsoft.Network/routeTables")[0]["properties"]["routes"][0]["properties"]
    assert (set(subnets), subnets["functions"]["delegations"][0]["properties"]["serviceName"],
            route["addressPrefix"], route["nextHopIpAddress"]) == (
        {"functions", "endpoints"}, "Microsoft.App/environments", "0.0.0.0/0", firewall_ip)


def test_spokes_get_disjoint_ranges_and_peer_only_with_their_hub():
    document = stack("lz-network")
    ranges = [ipaddress.ip_network(item["properties"]["addressSpace"]["addressPrefixes"][0])
              for item in of_type(document, "Microsoft.Network/virtualNetworks")]
    remotes = {re.search(r"virtualNetworks/([\w-]+)", item["properties"]["remoteVirtualNetwork"]["id"])[1]
               for item in of_type(document, "Microsoft.Network/virtualNetworks/virtualNetworkPeerings")}
    assert (all(not a.overlaps(b) for i, a in enumerate(ranges) for b in ranges[i + 1:]), remotes) == (
        True, {"vnet-hub-eastus2", "vnet-hub-centralus", "vnet-eastus2", "vnet-centralus"})


def test_local_egress_uses_a_nat_gateway_and_no_default_route():
    document = stack("lz-network", network={"egress": "local"})
    routes = [route["properties"]["addressPrefix"] for table in of_type(document, "Microsoft.Network/routeTables")
              for route in table["properties"]["routes"]]
    assert (len(of_type(document, "Microsoft.Network/natGateways")) > 0, "0.0.0.0/0" in routes) == (True, False)


def test_without_a_hub_spokes_stand_alone():
    document = stack("lz-network", network={"hub": False, "inspection": False})
    assert (of_type(document, "Microsoft.Network/azureFirewalls"),
            of_type(document, "Microsoft.Network/virtualNetworks/virtualNetworkPeerings"),
            len(of_type(document, "Microsoft.Network/natGateways")) > 0) == ([], [], True)


def test_a_vpn_link_gets_a_gateway_in_each_hub():
    document = stack("lz-network", network={"on_premises": "vpn"})
    gateways = of_type(document, "Microsoft.Network/virtualNetworkGateways")
    assert ([item["properties"]["gatewayType"] for item in gateways], "GatewaySubnet" in hub_subnets(
        document, "eastus2")) == (["Vpn", "Vpn"], True)


def test_declared_flows_are_firewall_rules_between_environment_ranges():
    flow = {"source": "dev", "destination": "stage", "port": 443, "reason": "Payments API"}
    document = stack("lz-network", network={"flows": [flow]})
    groups = of_type(document, "Microsoft.Network/firewallPolicies/ruleCollectionGroups")
    rules = [rule for group in groups for collection in group["properties"]["ruleCollections"]
             for rule in collection["rules"] if rule["name"] == "flow-1"]
    assert ({tuple(rule["destinationPorts"]) for rule in rules}, {rule["description"] for rule in rules}) == (
        {("443",)}, {"dev → stage on tcp/443: Payments API"})


def test_private_dns_zones_are_linked_to_every_hub_and_records_come_from_policy():
    document = stack("lz-network")
    zones = {item["name"] for item in of_type(document, "Microsoft.Network/privateDnsZones")}
    links = of_type(document, "Microsoft.Network/privateDnsZones/virtualNetworkLinks")
    dns = [item for item in of_type(document, "Microsoft.Authorization/policyAssignments")
           if item["identity"]["type"] == "SystemAssigned"]
    roles = of_type(document, "Microsoft.Authorization/roleAssignments")
    assert (zones, len(links), len(dns), {item["properties"]["roleDefinitionId"].rsplit("/", 1)[1] for item in roles},
            len(roles)) == (
        {"privatelink.blob.core.windows.net", "privatelink.documents.azure.com", "privatelink.servicebus.windows.net",
         "privatelink.vaultcore.azure.net"}, 8, 4, {NETWORK_CONTRIBUTOR}, 4)


# ---- lz-vault ----

def test_the_vault_keeps_teardown_backups_locked_for_sixty_days():
    document = stack("lz-vault")
    vaults = of_type(document, "Microsoft.DataProtection/backupVaults")
    [account] = of_type(document, "Microsoft.Storage/storageAccounts")
    security = vaults[0]["properties"]["securitySettings"]
    policy = account["properties"]["immutableStorageWithVersioning"]["immutabilityPolicy"]
    assert ([item["name"] for item in vaults], security["immutabilitySettings"]["state"],
            security["softDeleteSettings"]["state"], account["name"],
            (policy["state"], policy["immutabilityPeriodSinceCreationInDays"]),
            len(of_type(document, "Microsoft.DataProtection/resourceGuards"))) == (
        ["bv-teardown-eastus2", "bv-teardown-centralus"], "Locked", "AlwaysOn",
        "[concat('stteardown', uniqueString(subscription().id))]", ("Locked", 60), 2)


def test_only_backup_super_users_can_manage_the_vault():
    [role] = of_type(stack("lz-vault"), "Microsoft.Authorization/roleAssignments")
    assert (role["properties"]["principalId"], role["properties"]["roleDefinitionId"].rsplit("/", 1)[1]) == (
        GROUPS["backup_super_users"], "5e467623-bb1f-42f4-a55d-6e525e11384b")


def test_the_teardown_export_account_is_the_one_backups_go_to():
    from app.adapters.local_azure import AzureBackupStyle

    subscription = "5c0ffee0-0000-4000-8000-00000000b4c4"
    vault = AzureBackupStyle().vault(subscription, "eastus2", "Microsoft.DocumentDB/databaseAccounts")
    assert f"/storageAccounts/stteardown{unique_string(f'/subscriptions/{subscription}')}/" in vault


# ---- seed, workflow and README ----

def test_the_seed_creates_the_management_group_and_a_federated_identity_with_owner_there_only():
    script = files()["scripts/bootstrap-seed.sh"]
    assert ('az account management-group create --name "acme"' in script,
            '"subject":"repo:${REPOSITORY}:environment:landing-zone"' in script,
            '--scope "/providers/Microsoft.Management/managementGroups/acme"' in script,
            "/providers/Microsoft.Management/managementGroups/" + TENANT not in script,
            "a0bcee42-bf30-4d1b-926a-48d21664ef71" in script) == (True, True, True, True, True)


def test_an_mca_billing_scope_is_granted_by_hand():
    script = files(provider_answers={"billing_scope": MCA_SCOPE})["scripts/bootstrap-seed.sh"]
    assert ("a0bcee42-bf30-4d1b-926a-48d21664ef71" in script, "Azure subscription creator" in script) == (False, True)


def test_the_workflow_previews_then_applies_the_stacks_in_order():
    workflow = files()[".github/workflows/apply.yml"]
    order = [workflow.index(f'az stack mg create --name "{name}"') for name in STACKS]
    resolve = workflow.index("parameters/subscriptions.json")
    assert (order == sorted(order), workflow.count("az deployment mg what-if"), order[1] < resolve < order[2],
            "--action-on-unmanage detachAll" in workflow.split('--name "lz-subscriptions"')[1].split("az stack")[0],
            "client-id: ${{ vars.LZ_CLIENT_ID }}" in workflow) == (True, 6, True, True, True)


def test_the_readme_lists_the_stacks_and_what_is_left_to_a_person():
    readme = files(network={"on_premises": "vpn"})["README.md"]
    assert ("1. `stacks/lz-foundation`" in readme, "6. `stacks/lz-vault`" in readme,
            "VPN gateway" in readme, "scripts/bootstrap-seed.sh" in readme) == (True, True, True, True)
