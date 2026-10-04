import uuid

from fastapi.testclient import TestClient

from app.api.application import ApplicationFactory
from app.config import Settings
from tests.factories import TEST_DATABASE_URL, request_dict

JORDAN = {"X-Actor": "jordan", "X-Roles": "developer"}
SAM = {"X-Actor": "sam", "X-Roles": "reviewer"}
ALEX = {"X-Actor": "alex", "X-Roles": "platform-admin,reviewer"}


def create_project(client) -> None:
    client.post("/v1/projects", json=request_dict(), headers={"Idempotency-Key": "k-1"})


def simulate(client, environment: str = "stage", high_risk: bool = False):
    return client.post("/v1/projects/invoice-ingest/releases:simulate",
                       json={"environment": environment, "high_risk": high_risk}, headers=JORDAN)


def pipeline_plan(environment: str = "dev") -> dict:
    return {"project_name": "invoice-ingest", "environment": environment, "commit_sha": "4f78c64a1b2c",
            "artifact_digest": "sha256:aaaa",
            "changes": [{"action": "Add", "logical_id": "UploadsBucket", "resource_type": "AWS::S3::Bucket"}],
            "evidence": {"tests_passed": True, "signed": True}, "requested_by": "github-actions"}


def test_pipeline_submits_a_plan(client):
    create_project(client)
    response = client.post("/v1/releases", json=pipeline_plan())
    assert (response.status_code, response.json()["state"]) == (201, "deployed")


def test_simulated_stage_plan_waits_for_approval(client):
    create_project(client)
    assert simulate(client).json()["state"] == "awaiting_approval"


def test_simulated_high_risk_plan_needs_override(client):
    create_project(client)
    assert simulate(client, high_risk=True).json()["state"] == "override_requested"


def test_simulate_unknown_project(client):
    response = client.post("/v1/projects/nope/releases:simulate", json={"environment": "stage"}, headers=JORDAN)
    assert response.status_code == 404


def test_release_detail(client):
    create_project(client)
    release_id = simulate(client).json()["id"]
    assert client.get(f"/v1/releases/{release_id}").json()["requested_by"] == "jordan"


def test_unknown_release(client):
    assert client.get(f"/v1/releases/{uuid.uuid4()}").status_code == 404


def test_release_list(client):
    create_project(client)
    simulate(client)
    assert len(client.get("/v1/releases", params={"project": "invoice-ingest"}).json()) == 1


def test_reviewer_approves(client):
    create_project(client)
    release_id = simulate(client).json()["id"]
    response = client.post(f"/v1/releases/{release_id}:approve", json={"comment": "ok"}, headers=SAM)
    assert response.json()["state"] == "deployed"


def test_requester_cannot_approve(client):
    create_project(client)
    release_id = simulate(client).json()["id"]
    response = client.post(f"/v1/releases/{release_id}:approve", json={"comment": ""},
                           headers={"X-Actor": "jordan", "X-Roles": "reviewer"})
    assert response.status_code == 403


def test_reviewer_rejects(client):
    create_project(client)
    release_id = simulate(client).json()["id"]
    response = client.post(f"/v1/releases/{release_id}:reject", json={"comment": "no"}, headers=SAM)
    assert response.json()["state"] == "rejected"


def test_admin_approves_override(client):
    create_project(client)
    release_id = simulate(client, high_risk=True).json()["id"]
    response = client.post(f"/v1/releases/{release_id}:approve-override", json={"comment": "cache"}, headers=ALEX)
    assert response.json()["state"] == "awaiting_approval"


def test_inbox_for_reviewer(client):
    create_project(client)
    simulate(client)
    assert len(client.get("/v1/approvals/inbox", headers=SAM).json()) == 1


def test_project_pipeline(client):
    create_project(client)
    simulate(client, environment="dev")
    stages = client.get("/v1/projects/invoice-ingest/pipeline").json()
    assert stages[0]["release"]["state"] == "deployed"


def test_simulation_is_only_available_in_local_mode(session_factory, tmp_path):
    settings = Settings(database_url=TEST_DATABASE_URL, local_state_dir=str(tmp_path), github_mode="real")
    real_client = TestClient(ApplicationFactory(settings, session_factory=session_factory).create())
    response = real_client.post("/v1/projects/invoice-ingest/releases:simulate", json={"environment": "stage"})
    assert response.status_code == 404
