"""A Google Cloud project through the same flows as on AWS: provisioning, read-back and Change infrastructure."""

import json

import pytest

from app.adapters.factory import AdapterFactory
from app.adapters.local_gcp import LocalGcp
from app.adapters.local_github import LocalGitHub
from app.provisioning.worker import Worker
from app.readback.manifest import MANIFEST_PATH, ManifestSigner
from tests.gcp_helpers import DR, gcp_request, synthesize

OWNER = "acme-platform"
REPOSITORY = "invoice-ingest-infra"
PROJECT = "/v1/projects/invoice-ingest"
JORDAN = {"X-Actor": "jordan", "X-Roles": "developer"}


def github(settings) -> LocalGitHub:
    return LocalGitHub(settings.local_state_dir)


def run_worker(settings, session_factory) -> None:
    factory = AdapterFactory()
    Worker(session_factory, factory.github(settings), factory.clouds(settings), settings.github_owner,
           ManifestSigner.from_settings(settings)).process_one()


def provision(client, settings, session_factory, payload: dict) -> dict:
    client.post("/v1/projects", json=payload, headers={"Idempotency-Key": "k1"})
    run_worker(settings, session_factory)
    return client.get(f"{PROJECT}/repository:read-back").json()


@pytest.fixture
def provisioned(client, settings, session_factory) -> dict:
    return provision(client, settings, session_factory, gcp_request(resilience=DR, attach=True))


def files(settings) -> dict[str, str]:
    return github(settings).read_files(OWNER, REPOSITORY).files


# ---- provisioning ----

def test_provisioning_creates_a_sealed_terraform_repository(client, settings, provisioned):
    assert ({"main.tf.json", "variables.tf.json", "config/prod.tfvars", MANIFEST_PATH} <= set(files(settings)),
            client.get("/v1/projects").json()[0]["status"]) == (True, "active")


def test_every_environment_region_gets_workload_identity(settings, provisioned):
    stacks = LocalGcp(settings.local_state_dir).stacks()
    assert sorted((stack["account"], stack["region"]) for stack in stacks
                  if stack["account"].endswith("prod")) == [
        ("cloudinfra-payments-prod", "us-east1"), ("cloudinfra-payments-prod", "us-east4")]


def test_environment_variables_point_the_workflow_at_the_environment_project(settings, provisioned):
    variables = github(settings).environment(OWNER, REPOSITORY, "prod")
    assert (variables["GCP_PROJECT_ID"], variables["GCP_WORKLOAD_IDENTITY_PROVIDER"], variables["GCP_SECONDARY_REGION"],
            variables["SUBNETWORK_SECONDARY"]) == (
        "cloudinfra-payments-prod",
        "projects/cloudinfra-payments-prod/locations/global/workloadIdentityPools/cloudinfra-github/providers/github",
        "us-east4", "projects/cloudinfra-net-host/regions/us-east4/subnetworks/payments-prod")


def test_workflow_passes_the_cost_center_from_the_repository_variables(settings, provisioned):
    workflow = files(settings)[".github/workflows/deploy.yml"]
    assert ("org_cost_center=${{ vars.ORG_COST_CENTER }}" in workflow,
            github(settings).repository_variables(OWNER, REPOSITORY)["ORG_COST_CENTER"]) == (True, "CC-4410")


def test_deployments_are_named_after_the_project_and_region(settings, provisioned):
    workflow = files(settings)[".github/workflows/deploy.yml"]
    assert ("deployments/cloudinfra-invoice-ingest-${{ vars.GCP_PRIMARY_REGION }}" in workflow,
            "deployments/cloudinfra-invoice-ingest-${{ vars.GCP_SECONDARY_REGION }}" in workflow) == (True, True)


# ---- labels ----

def test_preview_shows_the_ownership_labels(client):
    labels = client.post("/v1/projects:preview", json=gcp_request()).json()["tags"]
    assert labels == {"org_portfolio": "pf-payments", "org_product": "pr-invoicing", "org_project": "invoice-ingest",
                      "org_cost_center": "cc-4410", "org_data_classification": "confidential",
                      "org_resilience": "single", "org_managed_by": "cloudinfra"}


def test_document_labels_carry_the_ownership():
    labels = synthesize(gcp_request())["locals"]["labels"]
    assert (labels["org_portfolio"], labels["org_product"], labels["org_data_classification"],
            labels["org_resilience"]) == ("pf-payments", "pr-invoicing", "confidential", "single")


def test_the_cost_center_has_no_default():
    assert "default" not in synthesize(gcp_request())["variable"]["org_cost_center"]


@pytest.mark.parametrize("tags, labels", [
    ({"org:cost-center": "CC 44/10"}, {"org_cost_center": "cc-44-10"}),
    ({"org:project": "x" * 70}, {"org_project": "x" * 63}),
])
def test_label_policy_keeps_keys_and_values_valid(tags, labels):
    from app.providers.gcp.labels import LabelPolicy

    assert LabelPolicy().format(tags) == labels


# ---- read-back ----

def test_read_back_returns_the_request(provisioned):
    assert (provisioned["verified"], provisioned["findings"], provisioned["request"]["provider"],
            provisioned["design"]["revision"]) == (True, [], "gcp", 1)


def test_hand_edited_configuration_blocks_read_back(client, settings, provisioned):
    github(settings).commit_files(OWNER, REPOSITORY, {"main.tf.json": "{}\n"}, "hand edit")
    result = client.get(f"{PROJECT}/repository:read-back").json()
    assert (result["verified"], result["findings"][0]["check"], result["findings"][0]["files"][0]["path"]) == (
        False, "integrity", "main.tf.json")


# ---- Change infrastructure ----

def change(provisioned: dict, resources: list[dict], connections: list[dict] | None = None) -> dict:
    request = {**provisioned["request"], "resources": resources,
               "connections": provisioned["request"]["connections"] if connections is None else connections}
    return {"request": request, "base_commit": provisioned["commit_sha"]}


def with_database(provisioned: dict) -> dict:
    return change(provisioned, [*provisioned["request"]["resources"], {"id": "orders", "type": "database.table",
                                                                       "config": {}}])


def test_change_preview_regenerates_the_configuration(client, provisioned):
    result = client.post(f"{PROJECT}/changes:preview", json=with_database(provisioned)).json()
    assert (result["summary"]["added_services"], result["summary"]["changed_files"],
            "google_firestore_database" in json.loads(result["files"]["main.tf.json"])["resource"]) == (
        ["orders"], ["infra.json", "main.tf.json"], True)


def test_removing_a_bucket_deletes_it_only_if_it_is_empty(client, provisioned):
    without_bucket = change(provisioned, [{"id": "processor", "type": "compute.function", "config": {}}], [])
    [removed] = client.post(f"{PROJECT}/changes:preview", json=without_bucket).json()["summary"]["removed_services"]
    assert removed == {"id": "uploads", "type": "storage.bucket", "retained": False,
                       "removal": "deleted only if empty"}


def test_change_opens_a_pull_request_that_says_what_happens_to_removed_services(client, settings, session_factory,
                                                                               provisioned):
    without_bucket = change(provisioned, [{"id": "processor", "type": "compute.function", "config": {}}], [])
    created = client.post(f"{PROJECT}/changes", json={**without_bucket, "confirm_removals": True},
                          headers=JORDAN).json()
    run_worker(settings, session_factory)
    pull_request = github(settings).pull_request(OWNER, REPOSITORY, 1)
    assert (client.get(f"{PROJECT}/changes/{created['id']}").json()["state"],
            "uploads (deleted only if empty)" in pull_request["body"]) == ("open", True)
