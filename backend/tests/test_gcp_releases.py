"""Release risk for Google Cloud: Terraform plan rows, which hold data and which change permissions."""

import pytest

from app.providers.gcp.provider import GcpProvider
from tests.gcp_helpers import gcp_request

JORDAN = {"X-Actor": "jordan", "X-Roles": "developer"}


def classifier():
    return GcpProvider().resources()


@pytest.mark.parametrize("type_name", ["google_storage_bucket", "google_firestore_database",
                                       "google_sql_database_instance", "google_alloydb_cluster",
                                       "google_spanner_database", "google_bigtable_instance",
                                       "google_pubsub_subscription", "google_kms_crypto_key",
                                       "google_secret_manager_secret"])
def test_data_holding_types_are_stateful(type_name):
    assert classifier().is_stateful(type_name) is True


def test_functions_hold_no_data():
    assert classifier().is_stateful("google_cloudfunctions2_function") is False


@pytest.mark.parametrize("type_name, permission", [
    ("google_storage_bucket_iam_member", True), ("google_project_iam_member", True),
    ("google_service_account", True), ("google_iam_deny_policy", True), ("google_org_policy_policy", True),
    ("google_cloud_run_service_iam_member", True), ("google_pubsub_topic", False),
])
def test_permission_types(type_name, permission):
    assert classifier().is_permission(type_name) is permission


def test_a_documents_plan_rows_are_its_resource_addresses():
    document = {"resource": {"google_storage_bucket": {"uploads": {}}, "google_pubsub_topic": {"jobs": {}}}}
    assert classifier().rows(document) == [("google_storage_bucket.uploads", "google_storage_bucket"),
                                           ("google_pubsub_topic.jobs", "google_pubsub_topic")]


# ---- Terraform plan JSON → release rows ----

def plan_change(address: str, type_name: str, actions: list[str]) -> dict:
    return {"address": address, "type": type_name, "mode": "managed", "change": {"actions": actions}}


def test_plan_actions_become_release_rows():
    from app.providers.gcp.releases import TerraformPlanReader

    plan = {"resource_changes": [
        plan_change("google_pubsub_topic.jobs", "google_pubsub_topic", ["create"]),
        plan_change("google_cloudfunctions2_function.processor", "google_cloudfunctions2_function", ["update"]),
        plan_change("google_pubsub_topic.old", "google_pubsub_topic", ["delete"]),
        plan_change("google_storage_bucket.uploads", "google_storage_bucket", ["delete", "create"]),
        plan_change("google_firestore_database.orders", "google_firestore_database", ["create", "delete"]),
        plan_change("google_service_account.processor", "google_service_account", ["no-op"]),
        {"address": "data.google_project.this", "type": "google_project", "mode": "data",
         "change": {"actions": ["read"]}},
    ]}
    assert [(row.action, row.logical_id, row.replacement) for row in TerraformPlanReader().changes(plan)] == [
        ("Add", "google_pubsub_topic.jobs", False), ("Modify", "google_cloudfunctions2_function.processor", False),
        ("Remove", "google_pubsub_topic.old", False), ("Modify", "google_storage_bucket.uploads", True),
        ("Modify", "google_firestore_database.orders", True)]


def test_a_plan_without_changes_has_no_rows():
    from app.providers.gcp.releases import TerraformPlanReader

    assert TerraformPlanReader().changes({"format_version": "1.2"}) == []


# ---- releases through the API ----

@pytest.fixture
def project(client):
    client.post("/v1/projects", json=gcp_request(), headers={"Idempotency-Key": "k1"})


def simulate(client, high_risk=False) -> dict:
    return client.post("/v1/projects/invoice-ingest/releases:simulate",
                       json={"environment": "stage", "high_risk": high_risk}, headers=JORDAN).json()


def test_a_release_lists_the_configuration_resources(client, project):
    rows = {change["logical_id"]: change["risk"] for change in simulate(client)["changes"]}
    assert (rows["google_storage_bucket.uploads"], rows["google_storage_bucket_iam_member.processor-uploads-events"],
            rows["google_cloudfunctions2_function.processor"]) == ("low", "medium", "low")


def test_replacing_a_bucket_is_high_risk(client, project):
    release = simulate(client, high_risk=True)
    replaced = [change for change in release["changes"] if change["replacement"]]
    assert (release["risk"], [change["logical_id"] for change in replaced]) == (
        "high", ["google_storage_bucket.uploads"])
