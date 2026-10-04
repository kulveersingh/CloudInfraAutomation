import pytest

from tests.lz_factories import account_op, add_account, add_ou, answers_dict

ALEX = {"X-Actor": "alex", "X-Roles": "platform-admin"}
RILEY = {"X-Actor": "riley", "X-Roles": "platform-admin"}
SAM = {"X-Actor": "sam", "X-Roles": "reviewer"}
BASE = "/v1/admin/landing-zone"


def request(edits: list[dict] | None = None, **overrides) -> dict:
    return {"answers": answers_dict(**overrides), "edits": edits or []}


def propose(client, edits=None, **overrides):
    return client.post(f"{BASE}:propose", json=request(edits, **overrides), headers=ALEX)


def create(client, headers=ALEX, edits=None, **overrides):
    return client.post(f"{BASE}/designs", json=request(edits, **overrides), headers=headers)


def ou_named(ous: list[dict], name: str) -> dict:
    for ou in ous:
        if ou["name"] == name:
            return ou
        found = ou_named(ou["children"], name) if ou["children"] else None
        if found:
            return found
    return {}


def submitted(client, edits=None) -> str:
    design_id = create(client, edits=edits).json()["id"]
    client.post(f"{BASE}/designs/{design_id}:submit", headers=ALEX)
    return design_id


def approve(client, design_id, headers=RILEY):
    return client.post(f"{BASE}/designs/{design_id}:approve", json={"comment": "Looks right"}, headers=headers)


# ---- propose (no persistence) ----

def test_propose_returns_the_ou_tree(client):
    assert [ou["name"] for ou in propose(client).json()["ous"]][:3] == ["Security", "Infrastructure", "Sandbox"]


def test_propose_reports_no_problems_for_recommended_answers(client):
    assert propose(client).json()["problems"] == []


def test_propose_includes_the_diagram(client):
    diagram = propose(client).json()["diagram"]
    assert (diagram["svg"].startswith("<svg"), diagram["mermaid"].startswith("flowchart TD")) == (True, True)


def test_propose_includes_the_generated_files(client):
    assert "stacks/lz-structure.yaml" in propose(client).json()["files"]


def test_propose_names_accounts_after_registry_portfolios(client):
    prod = next(ou for ou in propose(client).json()["ous"] if ou["name"] == "PROD")
    assert [account["name"] for account in prod["accounts"]] == ["acme-data-prod", "acme-payments-prod", "acme-retail-prod"]


def test_propose_rejects_invalid_answers(client):
    assert propose(client, governed_regions=["us-east-1"]).status_code == 422


def test_propose_requires_a_platform_admin(client):
    assert client.post(f"{BASE}:propose", json=request(), headers=SAM).status_code == 403


# ---- designs and approval ----

def test_create_saves_a_draft_version(client):
    response = create(client)
    assert (response.status_code, response.json()["version"], response.json()["status"]) == (201, 1, "draft")


def test_versions_increase(client):
    create(client)
    assert create(client).json()["version"] == 2


def test_create_requires_a_platform_admin(client):
    assert create(client, headers=SAM).status_code == 403


def test_list_designs(client):
    create(client)
    assert [design["version"] for design in client.get(f"{BASE}/designs", headers=ALEX).json()] == [1]


def test_get_design_includes_tree_and_diagram(client):
    design_id = create(client).json()["id"]
    detail = client.get(f"{BASE}/designs/{design_id}", headers=ALEX).json()
    assert (detail["ous"][0]["name"], detail["diagram"]["svg"][:4]) == ("Security", "<svg")


def test_unknown_design(client):
    assert client.get(f"{BASE}/designs/00000000-0000-0000-0000-000000000000", headers=ALEX).status_code == 404


def test_submit_moves_to_pending_approval(client):
    design_id = create(client).json()["id"]
    response = client.post(f"{BASE}/designs/{design_id}:submit", headers=ALEX)
    assert (response.json()["status"], response.json()["submitted_by"]) == ("pending_approval", "alex")


def test_submit_twice_conflicts(client):
    design_id = submitted(client)
    assert client.post(f"{BASE}/designs/{design_id}:submit", headers=ALEX).status_code == 409


def test_submit_requires_a_platform_admin(client):
    design_id = create(client).json()["id"]
    assert client.post(f"{BASE}/designs/{design_id}:submit", headers=SAM).status_code == 403


def test_submitter_cannot_approve(client):
    assert approve(client, submitted(client), headers=ALEX).status_code == 403


def test_reviewers_cannot_approve(client):
    assert approve(client, submitted(client), headers=SAM).status_code == 403


def test_draft_cannot_be_approved(client):
    assert approve(client, create(client).json()["id"]).status_code == 409


def test_second_admin_approval_applies_the_landing_zone(client):
    response = approve(client, submitted(client))
    assert (response.json()["status"], response.json()["decided_by"], response.json()["repository"]) == (
        "applied", "riley", "acme-platform/landing-zone-infra")


def test_approval_commits_the_repository(client, settings):
    approve(client, submitted(client))
    from pathlib import Path
    assert (Path(settings.local_state_dir) / "github" / "acme-platform" / "landing-zone-infra.git").is_dir()


def test_approval_records_the_commit(client):
    assert len(approve(client, submitted(client)).json()["commit_sha"]) == 40


def test_approval_registers_environment_networks(client):
    applied = approve(client, submitted(client)).json()
    account = applied["accounts"]["acme-payments-prod"]
    networks = client.get("/v1/admin/networks", params={"account_id": account}).json()
    assert ([network["region"] for network in networks], networks[0]["is_default"], networks[0]["cidr"]) == (
        ["us-east-1", "us-east-2"], True, "10.64.0.0/16")


def test_registered_network_carries_the_org_security_group(client):
    account = approve(client, submitted(client)).json()["accounts"]["acme-retail-dev"]
    network = client.get("/v1/admin/networks", params={"account_id": account}).json()[0]
    assert network["security_group_ids"][0].startswith("sg-")


def test_a_later_version_updates_the_same_repository(client):
    first = approve(client, submitted(client)).json()
    second = approve(client, submitted(client)).json()
    assert (second["repository"], second["commit_sha"] != first["commit_sha"]) == (first["repository"], True)


def test_reapplying_updates_registered_networks_in_place(client):
    first = approve(client, submitted(client)).json()
    approve(client, submitted(client))
    networks = client.get("/v1/admin/networks", params={"account_id": first["accounts"]["acme-payments-prod"]}).json()
    assert len(networks) == 2


def test_reject(client):
    response = client.post(f"{BASE}/designs/{submitted(client)}:reject", json={"comment": "Add PCI"}, headers=RILEY)
    assert (response.json()["status"], response.json()["decision_comment"]) == ("rejected", "Add PCI")


def test_rejected_design_cannot_be_approved(client):
    design_id = submitted(client)
    client.post(f"{BASE}/designs/{design_id}:reject", json={"comment": "No"}, headers=RILEY)
    assert approve(client, design_id).status_code == 409


def test_submitter_cannot_reject(client):
    response = client.post(f"{BASE}/designs/{submitted(client)}:reject", json={"comment": "No"}, headers=ALEX)
    assert response.status_code == 403


def test_diagram_endpoint_serves_svg(client):
    design_id = create(client).json()["id"]
    response = client.get(f"{BASE}/designs/{design_id}/diagram.svg", headers=ALEX)
    assert (response.headers["content-type"].startswith("image/svg+xml"), response.text[:4]) == (True, "<svg")


def test_submit_refuses_a_design_with_problems(client, monkeypatch):
    from app.landing_zone.validation import DesignRule, DesignValidator

    class AlwaysBroken(DesignRule):
        def problems(self, design):
            return ["Broken on purpose."]

    monkeypatch.setattr(DesignValidator, "default", classmethod(lambda cls: cls([AlwaysBroken()])))
    design_id = create(client).json()["id"]
    response = client.post(f"{BASE}/designs/{design_id}:submit", headers=ALEX)
    assert (response.status_code, response.json()["detail"]) == (422, "Broken on purpose.")


# ---- the OU tree editor ----

PAYMENTS = add_ou("Payments")


def test_propose_applies_the_edits(client):
    assert [child["name"] for child in ou_named(propose(client, [PAYMENTS]).json()["ous"], "PROD")["children"]] == [
        "Payments"]


def test_propose_reports_edits_that_no_longer_fit(client):
    assert propose(client, [add_ou("Acceptance", parent="uat")]).json()["problems"] == [
        "Edit 1 (add OU 'Acceptance' under 'uat'): OU 'uat' does not exist."]


def test_propose_rejects_unknown_edit_operations(client):
    assert propose(client, [{"op": "explode"}]).status_code == 422


def test_ous_describe_the_edits_they_allow(client):
    prod = ou_named(propose(client).json()["ous"], "PROD")
    assert (prod["custom"], prod["domain"], prod["allowed_edits"], prod["blocked_edits"]) == (
        False, "prod", ["add_child", "add_account"], {})


def test_non_empty_custom_ous_explain_why_they_cannot_be_removed(client):
    payments = ou_named(propose(client, [PAYMENTS, add_account("cards-prod", "custom_payments")]).json()["ous"], "Payments")
    assert (payments["custom"], payments["blocked_edits"]) == (
        True, {"remove": "Move its accounts and child OUs to another OU first."})


def test_accounts_describe_their_state_and_edits(client):
    prod = ou_named(propose(client, [account_op("disable_account", "acme-retail-prod")]).json()["ous"], "PROD")
    assert prod["accounts"][2] == {"name": "acme-retail-prod", "enabled": False, "added": False,
                                   "allowed_edits": ["move", "enable"]}


def test_create_stores_the_edits(client):
    assert create(client, edits=[PAYMENTS]).json()["edits"] == [PAYMENTS]


def test_get_design_applies_the_stored_edits(client):
    design_id = create(client, edits=[PAYMENTS]).json()["id"]
    detail = client.get(f"{BASE}/designs/{design_id}", headers=ALEX).json()
    assert ou_named(detail["ous"], "Payments")["domain"] == "prod"


def test_submit_refuses_edits_that_no_longer_fit(client):
    design_id = create(client, edits=[add_ou("Acceptance", parent="uat")]).json()["id"]
    assert client.post(f"{BASE}/designs/{design_id}:submit", headers=ALEX).status_code == 422


def test_approval_does_not_create_disabled_accounts(client):
    applied = approve(client, submitted(client, [account_op("disable_account", "acme-retail-prod")])).json()
    assert ("acme-retail-prod" in applied["accounts"], "acme-payments-prod" in applied["accounts"]) == (False, True)


# ---- industry templates and control packs ----

def test_list_templates_with_their_summary(client):
    templates = client.get(f"{BASE}/templates", headers=ALEX).json()
    saas = next(template for template in templates if template["id"] == "saas")
    assert ([template["id"] for template in templates], saas["environments"], saas["frameworks_verified"]) == (
        ["financial-services", "healthcare", "public-sector", "retail", "saas", "eu-sovereignty"],
        ["Sandbox", "DEV", "STAGE", "PROD"], False)


def test_template_summary_counts_ous_and_controls_by_behavior(client):
    saas = next(template for template in client.get(f"{BASE}/templates", headers=ALEX).json() if template["id"] == "saas")
    assert (saas["ou_count"] > 0, sorted(saas["control_counts"])) == (True, ["DETECTIVE", "PREVENTIVE", "PROACTIVE"])


def test_get_a_template(client):
    saas = client.get(f"{BASE}/templates/saas", headers=ALEX).json()
    assert (saas["version"], saas["answers"]["control_packs"][0], saas["edits"][0]["name"]) == (1, "foundation", "Tenants")


def test_unknown_template(client):
    assert client.get(f"{BASE}/templates/nope", headers=ALEX).status_code == 404


def test_templates_require_a_platform_admin(client):
    assert client.get(f"{BASE}/templates", headers=SAM).status_code == 403


def test_list_control_packs_with_their_controls(client):
    catalog = client.get(f"{BASE}/control-packs", headers=ALEX).json()
    foundation = catalog["packs"][0]
    assert (catalog["mappings_refreshed"], foundation["id"], foundation["selectors"], foundation["controls"][0]) == (
        None, "foundation", ["workloads"],
        {"id": "5kvme4m5d2b4d7if2fs5yg2ui", "name": "Disallow actions as a root user", "behavior": "PREVENTIVE",
         "severity": "HIGH", "implementation": "SCP", "frameworks": []})


def test_proposal_lists_the_controls_on_each_ou(client):
    prod = ou_named(propose(client).json()["ous"], "PROD")
    root_user = next(control for control in prod["controls"] if control["id"] == "5kvme4m5d2b4d7if2fs5yg2ui")
    assert root_user == {"id": "5kvme4m5d2b4d7if2fs5yg2ui", "name": "Disallow actions as a root user",
                         "behavior": "PREVENTIVE", "severity": "HIGH", "packs": ["foundation"]}


def test_proposal_carries_warnings_that_do_not_block(client):
    response = propose(client).json()
    assert (response["problems"], len(response["warnings"])) == ([], 1)


@pytest.mark.parametrize("template", ["financial-services", "healthcare", "public-sector", "retail", "saas",
                                      "eu-sovereignty"])
def test_every_template_proposes_through_the_api(client, template):
    chosen = client.get(f"{BASE}/templates/{template}", headers=ALEX).json()
    response = client.post(f"{BASE}:propose", headers=ALEX, json={
        "answers": {**answers_dict(), **chosen["answers"], "template": {"id": template, "version": chosen["version"]}},
        "edits": chosen["edits"]}).json()
    assert response["problems"] == []


def test_control_packs_include_the_profiles_they_make_up(client):
    assert client.get(f"{BASE}/control-packs", headers=ALEX).json()["profiles"]["baseline"] == ["foundation"]


def test_template_summary_counts_distinct_controls_and_their_enablements(client):
    saas = next(template for template in client.get(f"{BASE}/templates", headers=ALEX).json() if template["id"] == "saas")
    distinct = sum(saas["control_counts"].values())
    assert (distinct <= 51, saas["enabled_controls"] > distinct) == (True, True)
