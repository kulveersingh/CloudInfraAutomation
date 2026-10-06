"""The Azure landing zone's design (§22.12, MC-5a): provider answers, subscription naming, management groups and
subscriptions, the Azure Policy control snapshot and pack mappings, checks and advice, and templates proposing on
Azure."""

import re
from dataclasses import replace

import pytest
from pydantic import ValidationError

from app.landing_zone.answers import LandingZoneAnswers
from app.landing_zone.catalog.packs import PackRegistry
from app.landing_zone.catalog.templates import TemplateRegistry
from app.landing_zone.design import LandingZoneDesign, OuNode
from app.landing_zone.edits import TreeEditor
from app.landing_zone.validation import DesignAdvisor
from app.providers.azure.provider import AzureProvider
from tests.lz_factories import CATALOG, add_ou, answers_dict
from tests.test_lz_api import ALEX, BASE

TENANT = "8f2dd843-51d9-41e0-a23f-09119ffed634"
EA_SCOPE = "/providers/Microsoft.Billing/billingAccounts/1234567/enrollmentAccounts/7654321"
MCA_SCOPE = ("/providers/Microsoft.Billing/billingAccounts/a1b2c3d4-0000-4000-8000-000000000000:e5f6a7b8-0000-4000-"
             "8000-000000000000_2019-05-31/billingProfiles/AB12-CD34-EF5-GH6/invoiceSections/IJ78-KL90-MN1-OP2")
GROUPS = {"platform_admins": "11111111-1111-4111-8111-111111111111",
          "network_admins": "22222222-2222-4222-8222-222222222222",
          "security_admins": "33333333-3333-4333-8333-333333333333",
          "backup_super_users": "44444444-4444-4444-8444-444444444444"}
PROVIDER_ANSWERS = {"tenant_id": TENANT, "billing_scope": EA_SCOPE, "groups": GROUPS}
SHARED_KEYS = "8c6a50c6-9ffd-4ae7-986f-5fa6111f9a54"  # Storage accounts should prevent shared key access
FLOW_LOGS = "c251913d-7d24-4958-af87-478ed3b9ba41"  # Flow logs should be configured for every network security group
ALLOWED_LOCATIONS = "e56962a6-4747-49cd-b67b-bf8b01975c4c"
GUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
TEMPLATES = [template.id for template in TemplateRegistry.default().all()]


def toolkit():
    return AzureProvider().landing_zone()


def azure_answers_dict(**overrides) -> dict:
    base = answers_dict(home_region="eastus2", governed_regions=["eastus2", "centralus"])
    base.pop("management_email")
    provider_answers = {**PROVIDER_ANSWERS, **overrides.pop("provider_answers", {})}
    return {**base, "provider_answers": provider_answers, **overrides}


def design(edits=(), **overrides) -> LandingZoneDesign:
    built = toolkit().designer().design(LandingZoneAnswers.model_validate(azure_answers_dict(**overrides)), CATALOG)
    built.edit_problems = TreeEditor().apply(built, TreeEditor.parse(list(edits)))
    return built


def subscriptions(ou_name: str, **overrides) -> list[str]:
    return [account.name for account in design(**overrides).ou_named(ou_name).accounts]


def problems(built: LandingZoneDesign, checks=None) -> list[str]:
    return [*built.edit_problems, *[problem for check in (checks or toolkit().checks)
                                    for problem in check.problems(built, CATALOG)]]


def advice(built: LandingZoneDesign) -> list[str]:
    return DesignAdvisor.for_cloud(toolkit().controls, toolkit().advice).warnings(built)


# ---- provider answers ----

def test_azure_answers_default_to_foundational_defender_and_a_standard_firewall():
    answers = toolkit().answers.model_validate(PROVIDER_ANSWERS)
    assert (answers.groups.backup_super_users, answers.defender, answers.firewall_tier) == (
        GROUPS["backup_super_users"], "foundational", "standard")


def test_an_mca_invoice_section_is_a_billing_scope():
    assert toolkit().answers.model_validate({**PROVIDER_ANSWERS, "billing_scope": MCA_SCOPE}).billing_scope == MCA_SCOPE


@pytest.mark.parametrize("change", [
    {"tenant_id": "acme"}, {"billing_scope": "/providers/Microsoft.Billing/billingAccounts/1234567"},
    {"defender": "gold"}, {"firewall_tier": "basic"}, {"groups": {**GROUPS, "platform_admins": "admins"}},
    {"groups": {key: value for key, value in GROUPS.items() if key != "backup_super_users"}},
])
def test_azure_answers_are_checked(change):
    with pytest.raises(ValidationError):
        toolkit().answers.model_validate({**PROVIDER_ANSWERS, **change})


# ---- management groups and subscriptions ----

def test_subscriptions_are_named_after_the_organization():
    assert subscriptions("PROD") == ["acme-payments-prod", "acme-retail-prod"]


def test_subscriptions_have_no_email():
    assert {account.email for account in design().walk_accounts()} == {None}


def test_the_security_management_group_holds_management_and_security_subscriptions():
    assert subscriptions("Security") == ["acme-management", "acme-security", "acme-security-tooling"]


def test_the_infrastructure_management_group_holds_connectivity_and_the_shared_subscriptions():
    assert subscriptions("Infrastructure") == ["acme-connectivity", "acme-shared-services", "acme-identity",
                                               "acme-backup", "acme-monitoring"]


def test_spokes_live_in_the_workload_subscriptions_so_environments_have_no_host():
    assert [name for name in subscriptions("DEV") if "net" in name or "connectivity" in name] == []


def test_nothing_is_created_by_an_azure_service():
    assert [ou.name for ou in design().walk() if ou.created_by_service] == []


# ---- the control snapshot and pack mappings ----

def test_every_pack_has_azure_controls():
    mappings = toolkit().controls.mappings
    assert [pack.id for pack in PackRegistry.default().all() if not mappings.controls_for(pack.id)] == []


def test_controls_are_built_in_definitions_by_id_or_the_platforms_own():
    controls = toolkit().controls.snapshot.controls.values()
    assert [control.id for control in controls if not (
        (control.implementation == "BUILT_IN_POLICY" and GUID.match(control.id))
        or (control.implementation == "CUSTOM_POLICY" and control.id.startswith("cloudinfra-")))] == []


def test_preventive_controls_deny_and_detective_ones_audit():
    snapshot = toolkit().controls.snapshot
    assert ((snapshot.get(SHARED_KEYS).behavior, snapshot.get(SHARED_KEYS).name),
            (snapshot.get(FLOW_LOGS).behavior, snapshot.get(FLOW_LOGS).name)) == (
        ("PREVENTIVE", "Storage accounts should prevent shared key access"),
        ("DETECTIVE", "Flow logs should be configured for every network security group"))


def test_every_control_names_the_effect_it_is_assigned_with():
    from app.providers.azure.landing_zone.controls import azure_effects

    effects = azure_effects()
    snapshot = toolkit().controls.snapshot
    allowed = {"PREVENTIVE": {"Deny", "DenyAction"}, "DETECTIVE": {"Audit", "AuditIfNotExists"}}
    assert [control.id for control in snapshot.controls.values()
            if effects[control.id] not in allowed[control.behavior]] == []


def test_azure_has_no_proactive_controls():
    assert [control.id for control in toolkit().controls.snapshot.controls.values()
            if control.behavior == "PROACTIVE"] == []


def test_every_control_goes_on_the_top_most_management_group_because_azure_policy_inherits_them_all():
    controls = toolkit().resolver().resolve(design([add_ou("Payments")])).controls
    on_prod = [item.control.id for item in controls["prod"]]
    assert ((SHARED_KEYS in on_prod, FLOW_LOGS in on_prod), controls.get("custom_payments", [])) == ((True, True), [])


def test_data_residency_allows_the_governed_regions():
    controls = toolkit().resolver().resolve(design(control_packs=["data-residency"])).controls["prod"]
    locations = next(item for item in controls if item.control.id == ALLOWED_LOCATIONS)
    assert locations.parameters == {"AllowedRegions": ["eastus2", "centralus"]}


def test_frameworks_are_unverified_until_the_snapshot_is_refreshed():
    assert toolkit().controls.snapshot.mappings_refreshed is None


# ---- checks ----

def test_management_groups_nest_at_most_six_below_the_tenant_root():
    """The organization's own management group takes the first level (MC5-3)."""
    edits, parent = [], "prod"
    for level in range(5):
        edits.append(add_ou(f"Level{level}", parent=parent))
        parent = f"custom_level{level}"
    assert problems(design(edits)) == ["Management group 'Level4' is 7 levels below the tenant root; Azure allows 6."]


def test_management_group_ids_are_at_most_ninety_characters():
    built = design()
    built.ou_named("PROD").children = [OuNode(key="k" * 90, name="Long", kind="custom")]
    assert problems(built) == [f"Management group id 'acme-{'k' * 90}' is 95 characters; Azure allows 90."]


def test_subscription_names_are_checked():
    built = design()
    built.ou_named("PROD").accounts.append(replace(built.ou_named("PROD").accounts[0], name="x" * 65))
    built.ou_named("DEV").accounts.append(replace(built.ou_named("PROD").accounts[0]))
    assert problems(built) == ["Subscription name '" + "x" * 65 + "' is 65 characters; Azure allows 64.",
                               "Subscription name 'acme-payments-prod' is used twice."]


def test_governed_regions_need_their_pairs_for_dr_and_ha_storage():
    assert problems(design(governed_regions=["eastus2", "westus2"])) == [
        ("Governed region eastus2 pairs with centralus, which is not governed: geo-redundant storage there cannot "
         "replicate for DR and HA."),
        ("Governed region westus2 pairs with westcentralus, which is not governed: geo-redundant storage there cannot "
         "replicate for DR and HA.")]


def test_a_scope_takes_a_limited_number_of_policy_assignments():
    from app.providers.azure.landing_zone.limits import PolicyAssignmentsPerScope

    built = design()
    assigned = len(toolkit().resolver().resolve(built).controls["prod"])
    assert (f"Management group 'PROD' gets {assigned} policy assignments; Azure allows 5 per scope."
            in problems(built, (PolicyAssignmentsPerScope(limit=5),)))


def test_recommended_answers_have_no_problems():
    assert problems(design()) == []


# ---- advice ----

WITHOUT_IDENTITY = ["network", "shared_services", "backup", "monitoring"]


def test_paid_defender_plans_are_advised_with_their_cost():
    found = advice(design(infrastructure=WITHOUT_IDENTITY, provider_answers={"defender": "standard"}))
    assert any(warning.startswith("Defender plans are billed per subscription") for warning in found)


def test_local_egress_skips_the_firewall():
    found = advice(design(infrastructure=WITHOUT_IDENTITY, network={"egress": "local"}))
    assert ("Local egress uses a NAT gateway in each spoke, so outbound traffic does not pass the hub's firewall."
            in found)


def test_strict_residency_warns_about_paired_region_storage():
    found = advice(design(infrastructure=WITHOUT_IDENTITY, control_packs=["foundation", "strict-residency"]))
    assert ("Strict residency denies geo-redundant storage whose pair is outside the governed regions, so DR/HA "
            "projects with storage need both regions of a pair governed.") in found


def test_the_identity_subscription_is_only_for_domain_controllers():
    assert ("The Identity subscription is only needed for AD DS domain controllers; Entra ID needs none."
            in advice(design()))


def test_large_designs_need_room_on_the_billing_account():
    found = advice(design(infrastructure=WITHOUT_IDENTITY, account_model="product",
                          environment_ids=["sandbox", "dev", "qa", "test", "uat", "perf", "stage", "prod"]))
    assert any(warning.startswith("This design creates ") and "billing account" in warning for warning in found)


def test_recommended_design_without_identity_has_no_advice():
    assert advice(design(infrastructure=WITHOUT_IDENTITY)) == []


# ---- through the API ----

def azure_request(**overrides) -> dict:
    return {"provider": "azure", "answers": azure_answers_dict(**overrides), "edits": []}


def test_propose_an_azure_landing_zone(client):
    body = client.post(f"{BASE}:propose", json=azure_request(), headers=ALEX).json()
    assert (body["problems"], [ou["name"] for ou in body["ous"]][:2], "design.json" in body["files"],
            "docs/controls.md" in body["files"]) == ([], ["Security", "Infrastructure"], True, True)


def test_invalid_azure_answers_are_refused(client):
    response = client.post(f"{BASE}:propose", json=azure_request(provider_answers={"tenant_id": "acme"}), headers=ALEX)
    assert (response.status_code, response.json()["detail"]) == (422, "Invalid provider answers: tenant_id.")


def test_the_diagram_names_the_tenant_and_the_organizations_management_group(client):
    svg = client.post(f"{BASE}:propose", json=azure_request(), headers=ALEX).json()["diagram"]["svg"]
    assert (f"Tenant {TENANT}" in svg, "Management group acme" in svg) == (True, True)


def test_the_controls_document_explains_inheritance(client):
    files = client.post(f"{BASE}:propose", json=azure_request(), headers=ALEX).json()["files"]
    assert ("# Azure controls: acme" in files["docs/controls.md"], f"`{SHARED_KEYS}`" in files["docs/controls.md"]) == (
        True, True)


def test_control_packs_list_azure_controls(client):
    packs = client.get(f"{BASE}/control-packs", params={"provider": "azure"}, headers=ALEX).json()["packs"]
    foundation = next(pack for pack in packs if pack["id"] == "foundation")
    assert SHARED_KEYS in [control["id"] for control in foundation["controls"]]


@pytest.mark.parametrize("template", TEMPLATES)
def test_every_template_proposes_on_azure_without_problems(client, template):
    details = client.get(f"{BASE}/templates/{template}", params={"provider": "azure"}, headers=ALEX).json()
    answers = {**azure_answers_dict(), **details["answers"]}
    body = client.post(f"{BASE}:propose", json={"provider": "azure", "answers": answers, "edits": details["edits"]},
                       headers=ALEX).json()
    assert body["problems"] == []


def test_templates_choose_azure_regions_in_pairs():
    template = TemplateRegistry.default().get("eu-sovereignty")
    assert (template.answers_for("azure")["home_region"], template.answers_for("azure")["governed_regions"]) == (
        "westeurope", ["westeurope", "northeurope"])


def test_template_summaries_count_azure_controls(client):
    summaries = client.get(f"{BASE}/templates", params={"provider": "azure"}, headers=ALEX).json()
    saas = next(summary for summary in summaries if summary["id"] == "saas")
    assert (saas["control_counts"]["PROACTIVE"], saas["control_counts"]["PREVENTIVE"] > 0) == (0, True)


def test_the_landing_zone_repository_is_azures_own():
    assert toolkit().repository_name == "landing-zone-azure-infra"
