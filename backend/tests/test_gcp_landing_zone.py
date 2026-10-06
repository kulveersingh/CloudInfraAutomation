"""The Google Cloud landing zone's design (§22.10, MC-3b): provider answers, project naming, folders and projects,
the control catalog and pack mappings, checks and advice, and templates proposing on Google Cloud."""

import hashlib

import pytest
from pydantic import ValidationError

from app.landing_zone.answers import LandingZoneAnswers
from app.landing_zone.catalog.packs import PackRegistry
from app.landing_zone.catalog.templates import TemplateRegistry
from app.landing_zone.design import LandingZoneDesign, OuNode
from app.landing_zone.edits import TreeEditor
from app.landing_zone.validation import DesignAdvisor
from app.providers.gcp.provider import GcpProvider
from tests.lz_factories import CATALOG, add_ou, answers_dict
from tests.test_lz_api import ALEX, BASE, RILEY

ORGANIZATION_ID = "123456789012"
H4 = hashlib.sha1(ORGANIZATION_ID.encode()).hexdigest()[:4]
PROVIDER_ANSWERS = {"organization_id": ORGANIZATION_ID, "billing_account": "01ABCD-23EF45-67GH89",
                    "domain": "acme.example"}
KEY_CREATION = "constraints/iam.disableServiceAccountKeyCreation"
MFA = "MFA_NOT_ENFORCED"
TEMPLATES = [template.id for template in TemplateRegistry.default().all()]


def toolkit():
    return GcpProvider().landing_zone()


def gcp_answers_dict(**overrides) -> dict:
    base = answers_dict(home_region="us-east1", governed_regions=["us-east1", "us-east4"])
    base.pop("management_email")
    provider_answers = {**PROVIDER_ANSWERS, **overrides.pop("provider_answers", {})}
    return {**base, "provider_answers": provider_answers, **overrides}


def design(edits=(), **overrides) -> LandingZoneDesign:
    built = toolkit().designer().design(LandingZoneAnswers.model_validate(gcp_answers_dict(**overrides)), CATALOG)
    built.edit_problems = TreeEditor().apply(built, TreeEditor.parse(list(edits)))
    return built


def projects(ou_name: str, **overrides) -> list[str]:
    return [account.name for account in design(**overrides).ou_named(ou_name).accounts]


def problems(built: LandingZoneDesign) -> list[str]:
    return [*built.edit_problems, *[problem for check in toolkit().checks for problem in check.problems(built, CATALOG)]]


def advice(built: LandingZoneDesign) -> list[str]:
    return DesignAdvisor.for_cloud(toolkit().controls, toolkit().advice).warnings(built)


# ---- provider answers ----

def test_google_cloud_answers_name_the_admin_groups_in_the_domain():
    answers = toolkit().answers.model_validate(PROVIDER_ANSWERS)
    assert (answers.groups.organization_admins, answers.groups.backup_super_users, answers.scc_tier) == (
        "gcp-organization-admins@acme.example", "gcp-backup-super-users@acme.example", "premium")


@pytest.mark.parametrize("change", [{"organization_id": "acme"}, {"billing_account": "123"}, {"domain": "acme"},
                                    {"scc_tier": "gold"}, {"groups": {"organization_admins": "admins"}}])
def test_google_cloud_answers_are_checked(change):
    with pytest.raises(ValidationError):
        toolkit().answers.model_validate({**PROVIDER_ANSWERS, **change})


# ---- folders and projects ----

def test_project_ids_carry_an_organization_hash():
    assert projects("PROD") == [f"acme-payments-prod-{H4}", f"acme-retail-prod-{H4}", f"acme-net-prod-{H4}"]


def test_projects_have_no_email():
    assert {account.email for account in design().walk_accounts()} == {None}


def test_the_security_folder_holds_logging_and_security_projects():
    assert projects("Security") == [f"acme-logging-{H4}", f"acme-security-{H4}", f"acme-security-tooling-{H4}"]


def test_the_infrastructure_folder_holds_the_hub_shared_services_vault_and_monitoring():
    assert projects("Infrastructure") == [f"acme-net-hub-{H4}", f"acme-shared-services-{H4}", f"acme-vault-{H4}",
                                          f"acme-monitoring-{H4}"]


def test_each_workload_environment_has_its_shared_vpc_host_project():
    assert (projects("DEV")[-1], f"acme-net-sandbox-{H4}" in projects("Sandbox")) == (f"acme-net-dev-{H4}", False)


def test_nothing_is_created_by_a_google_cloud_service():
    assert [ou.name for ou in design().walk() if ou.created_by_service] == []


# ---- the control catalog and pack mappings ----

def test_every_pack_has_google_cloud_controls():
    mappings = toolkit().controls.mappings
    assert [pack.id for pack in PackRegistry.default().all() if not mappings.controls_for(pack.id)] == []


def test_preventive_controls_are_org_policy_constraints_and_detective_ones_scc_detectors():
    snapshot = toolkit().controls.snapshot
    assert ((snapshot.get(KEY_CREATION).behavior, snapshot.get(KEY_CREATION).implementation),
            (snapshot.get(MFA).behavior, snapshot.get(MFA).implementation)) == (
        ("PREVENTIVE", "ORG_POLICY"), ("DETECTIVE", "SCC_DETECTOR"))


def test_google_cloud_has_no_proactive_controls():
    assert [control.id for control in toolkit().controls.snapshot.controls.values()
            if control.behavior == "PROACTIVE"] == []


def test_every_control_goes_on_the_top_most_folder_because_google_cloud_inherits_them_all():
    controls = toolkit().resolver().resolve(design([add_ou("Payments")])).controls
    on_prod = [item.control.id for item in controls["prod"]]
    assert ((KEY_CREATION in on_prod, MFA in on_prod), controls.get("custom_payments", [])) == ((True, True), [])


def test_data_residency_allows_the_governed_regions():
    controls = toolkit().resolver().resolve(design(control_packs=["data-residency"])).controls["prod"]
    locations = next(item for item in controls if item.control.id == "constraints/gcp.resourceLocations")
    assert locations.parameters == {"AllowedRegions": ["us-east1", "us-east4"]}


def test_frameworks_are_unverified_until_the_snapshot_is_refreshed():
    assert toolkit().controls.snapshot.mappings_refreshed is None


# ---- checks ----

def test_folders_nest_at_most_ten_deep():
    edits, parent = [], "prod"
    for level in range(10):
        edits.append(add_ou(f"Level{level}", parent=parent))
        parent = f"custom_level{level}"
    assert problems(design(edits)) == ["Folder 'Level9' is 11 levels deep; Google Cloud allows 10."]


def test_at_most_three_hundred_folders_under_one_parent():
    built = design()
    built.ou_named("PROD").children = [OuNode(key=f"f{index}", name=f"F{index}", kind="custom") for index in range(301)]
    assert problems(built) == ["Folder 'PROD' has 301 folders; Google Cloud allows 300 under one parent."]


def test_a_long_project_id_is_a_problem():
    found = problems(design(organization_name="acme-holdings-group"))
    assert f"Project id 'acme-holdings-group-shared-services-{H4}' is 40 characters; Google Cloud allows 6 to 30." in found


def test_recommended_answers_have_no_problems():
    assert problems(design()) == []


# ---- advice ----

def test_detective_controls_need_premium_or_enterprise():
    assert advice(design(provider_answers={"scc_tier": "standard"})) == [
        ("Detective controls are not deployed: Security Command Center Standard has no postures. "
         "Choose Premium or Enterprise to deploy them.")]


def test_central_egress_is_not_used_on_google_cloud():
    assert "Google Cloud has no central egress VPC: each environment's VPC uses Cloud NAT." in advice(design())


def test_strict_residency_warns_about_dual_region_storage():
    found = advice(design(control_packs=["foundation", "strict-residency"]))
    assert ("Strict residency blocks dual-region buckets and multi-region Firestore, so DR/HA projects in these "
            "folders cannot use them.") in found


def test_large_designs_need_a_project_quota():
    found = advice(design(account_model="product", environment_ids=["sandbox", "dev", "qa", "test", "uat", "perf",
                                                                      "stage", "prod"]))
    assert any(warning.startswith("This design creates ") and "project quota" in warning for warning in found)


def test_recommended_local_egress_design_has_no_advice():
    assert advice(design(network={"egress": "local"})) == []


# ---- through the API ----

def gcp_request(**overrides) -> dict:
    return {"provider": "gcp", "answers": gcp_answers_dict(**overrides), "edits": []}


def test_propose_a_google_cloud_landing_zone(client):
    body = client.post(f"{BASE}:propose", json=gcp_request(network={"egress": "local"}), headers=ALEX).json()
    assert (body["problems"], [ou["name"] for ou in body["ous"]][:2], "design.json" in body["files"],
            "docs/controls.md" in body["files"]) == ([], ["Security", "Infrastructure"], True, True)


def test_invalid_google_cloud_answers_are_refused(client):
    response = client.post(f"{BASE}:propose", json=gcp_request(provider_answers={"organization_id": "acme"}),
                           headers=ALEX)
    assert (response.status_code, response.json()["detail"]) == (422, "Invalid provider answers: organization_id.")


def test_the_diagram_names_the_organization(client):
    body = client.post(f"{BASE}:propose", json=gcp_request(), headers=ALEX).json()
    assert f"Organization {ORGANIZATION_ID}" in body["diagram"]["svg"]


def test_control_packs_list_google_cloud_controls(client):
    packs = client.get(f"{BASE}/control-packs", params={"provider": "gcp"}, headers=ALEX).json()["packs"]
    foundation = next(pack for pack in packs if pack["id"] == "foundation")
    assert KEY_CREATION in [control["id"] for control in foundation["controls"]]


@pytest.mark.parametrize("template", TEMPLATES)
def test_every_template_proposes_on_google_cloud_without_problems(client, template):
    details = client.get(f"{BASE}/templates/{template}", params={"provider": "gcp"}, headers=ALEX).json()
    answers = {**gcp_answers_dict(), **details["answers"]}
    body = client.post(f"{BASE}:propose", json={"provider": "gcp", "answers": answers, "edits": details["edits"]},
                       headers=ALEX).json()
    assert body["problems"] == []


def test_templates_choose_google_cloud_regions():
    template = TemplateRegistry.default().get("eu-sovereignty")
    assert (template.answers_for("gcp")["home_region"], template.answers_for("gcp")["governed_regions"],
            template.answers_for("aws")["home_region"]) == (
        "europe-west3", ["europe-west3", "europe-west1"], "eu-central-1")


def test_template_summaries_count_google_cloud_controls(client):
    summaries = client.get(f"{BASE}/templates", params={"provider": "gcp"}, headers=ALEX).json()
    saas = next(summary for summary in summaries if summary["id"] == "saas")
    assert (saas["control_counts"]["PROACTIVE"], saas["control_counts"]["PREVENTIVE"] > 0) == (0, True)


def test_applying_a_google_cloud_landing_zone_is_not_available_yet(client):
    design_id = client.post(f"{BASE}/designs", json=gcp_request(network={"egress": "local"}), headers=ALEX).json()["id"]
    client.post(f"{BASE}/designs/{design_id}:submit", headers=ALEX)
    response = client.post(f"{BASE}/designs/{design_id}:approve", json={"comment": "ok"}, headers=RILEY)
    assert (response.status_code, response.json()["detail"]) == (
        422, "Applying a Google Cloud landing zone is not available yet.")
