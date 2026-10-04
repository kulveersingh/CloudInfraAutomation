import uuid

from tests.factories import dr_request_dict, request_dict


def preview(client, payload: dict):
    return client.post("/v1/projects:preview", json=payload)


def create(client, payload: dict, key: str | None = "key-1"):
    headers = {"Idempotency-Key": key} if key else {}
    return client.post("/v1/projects", json=payload, headers=headers)


# ---- health, registry, catalog ----

def test_health(client):
    assert client.get("/healthz").json() == {"status": "ok"}


def test_org_registry(client):
    assert len(client.get("/v1/org-registry").json()) == 3


def test_catalog(client):
    assert "s3.bucket" in [entry["type"] for entry in client.get("/v1/catalog").json()]


def test_environments(client):
    assert [item["id"] for item in client.get("/v1/environments").json()] == [
        "sandbox", "dev", "test", "stage", "prod"]


# ---- admin: regions ----

def test_list_regions(client):
    assert len(client.get("/v1/admin/regions").json()) == 6


def test_enable_region(client):
    response = client.put("/v1/admin/regions/ap-southeast-2", json={"enabled": True})
    assert response.json()["enabled"] is True


def test_enable_unknown_region(client):
    assert client.put("/v1/admin/regions/mars-1", json={"enabled": True}).status_code == 404


# ---- admin: cost centers ----

def test_get_cost_centers(client):
    assert client.get("/v1/admin/cost-centers").json()["default"] == "CC-1000"


def test_update_cost_centers(client):
    response = client.put("/v1/admin/cost-centers", json={"default": "CC-2000"})
    assert response.json()["default"] == "CC-2000"


def test_update_cost_centers_invalid(client):
    response = client.put("/v1/admin/cost-centers", json={"default": "bad"})
    assert (response.status_code, "bad" in response.json()["detail"]) == (422, True)


# ---- preview ----

def test_preview_returns_files(client):
    assert "template.yaml" in preview(client, request_dict()).json()["files"]


def test_preview_resolves_tags(client):
    tags = preview(client, request_dict()).json()["tags"]
    assert (tags["org:project"], tags["org:cost-center"], tags["org:portfolio"]) == (
        "invoice-ingest", "CC-4410", "pf-payments")


def test_preview_resolves_target_accounts(client):
    target = preview(client, request_dict()).json()["targets"]["prod"]
    assert (target["account_id"], target["regions"]) == ("555555555555", ["us-east-1"])


def test_preview_dr_targets_both_regions(client):
    assert preview(client, dr_request_dict()).json()["targets"]["prod"]["regions"] == ["us-east-1", "us-east-2"]


def test_preview_has_no_lint_findings(client):
    assert preview(client, request_dict()).json()["lint"] == []


def test_preview_rejects_malformed_payload(client):
    assert preview(client, request_dict(project_name="X")).status_code == 422


def test_preview_rejects_semantic_problems(client):
    payload = request_dict(connections=[{"kind": "event.notify", "source": "processor", "target": "uploads"}])
    assert "cannot connect" in preview(client, payload).json()["detail"]


def test_preview_rejects_foreign_product(client):
    ownership = {"portfolio_id": "pf-payments", "product_id": "pr-storefront", "data_classification": "internal"}
    assert preview(client, request_dict(ownership=ownership)).status_code == 422


def test_preview_unknown_portfolio(client):
    ownership = {"portfolio_id": "pf-nope", "product_id": "pr-invoicing", "data_classification": "internal"}
    assert preview(client, request_dict(ownership=ownership)).status_code == 404


def test_preview_unknown_environment(client):
    assert "Unknown environment" in preview(client, request_dict(environments=["dev", "qa9"])).json()["detail"]


def test_preview_disabled_region(client):
    payload = request_dict(resilience={"mode": "dr", "primary_region": "us-east-1",
                                       "secondary_region": "ap-southeast-2"})
    assert preview(client, payload).status_code == 422


# ---- create + jobs ----

def test_create_accepts_and_returns_job(client):
    response = create(client, request_dict())
    assert (response.status_code, "job_id" in response.json()) == (202, True)


def test_created_job_is_queued(client):
    job_id = create(client, request_dict()).json()["job_id"]
    assert client.get(f"/v1/jobs/{job_id}").json()["state"] == "queued"


def test_create_is_idempotent(client):
    assert create(client, request_dict()).json() == create(client, request_dict()).json()


def test_create_conflicts_with_existing_project(client):
    create(client, request_dict())
    assert create(client, request_dict(), key="key-2").status_code == 409


def test_create_reused_key_with_other_payload(client):
    create(client, request_dict())
    assert create(client, request_dict(project_name="other-app")).status_code == 409


def test_create_requires_idempotency_key(client):
    assert create(client, request_dict(), key=None).status_code == 400


def test_create_validates_like_preview(client):
    assert create(client, request_dict(environments=["qa9"])).status_code == 422


def test_projects_list(client):
    create(client, request_dict())
    assert client.get("/v1/projects").json() == [{
        "name": "invoice-ingest", "portfolio_id": "pf-payments", "product_id": "pr-invoicing",
        "resilience_mode": "single", "status": "provisioning"}]


def test_job_has_steps_list(client):
    job_id = create(client, request_dict()).json()["job_id"]
    assert client.get(f"/v1/jobs/{job_id}").json()["steps"] == []


def test_unknown_job(client):
    assert client.get(f"/v1/jobs/{uuid.uuid4()}").status_code == 404


def test_malformed_job_id(client):
    assert client.get("/v1/jobs/not-a-uuid").status_code == 422


def test_cors_allows_local_ui(client):
    response = client.options("/healthz", headers={"Origin": "http://localhost:5173",
                                                   "Access-Control-Request-Method": "GET"})
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
