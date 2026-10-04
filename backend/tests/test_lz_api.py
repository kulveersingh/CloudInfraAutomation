from tests.lz_factories import answers_dict

ALEX = {"X-Actor": "alex", "X-Roles": "platform-admin"}
RILEY = {"X-Actor": "riley", "X-Roles": "platform-admin"}
SAM = {"X-Actor": "sam", "X-Roles": "reviewer"}
BASE = "/v1/admin/landing-zone"


def propose(client, **overrides):
    return client.post(f"{BASE}:propose", json=answers_dict(**overrides), headers=ALEX)


def create(client, headers=ALEX, **overrides):
    return client.post(f"{BASE}/designs", json=answers_dict(**overrides), headers=headers)


def submitted(client) -> str:
    design_id = create(client).json()["id"]
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
    assert prod["accounts"] == ["acme-payments-prod", "acme-retail-prod", "acme-data-prod"]


def test_propose_rejects_invalid_answers(client):
    assert propose(client, governed_regions=["us-east-1"]).status_code == 422


def test_propose_requires_a_platform_admin(client):
    assert client.post(f"{BASE}:propose", json=answers_dict(), headers=SAM).status_code == 403


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
