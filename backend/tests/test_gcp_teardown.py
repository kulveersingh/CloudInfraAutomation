"""Teardown and restore on Google Cloud (§22.9.5): data stores from the Terraform configuration, backups into a
Bucket-Locked bucket (or the Backup and DR vault) in the vault project, and restore with import."""

import hashlib
from datetime import UTC, datetime, timedelta

import pytest

from app.adapters.factory import AdapterFactory
from app.adapters.local_gcp import LocalGcp
from app.adapters.local_github import LocalGitHub
from app.config import Settings
from app.provisioning.worker import Worker
from app.readback.manifest import ManifestSigner
from tests.factories import TEST_DATABASE_URL
from tests.gcp_helpers import DR, gcp_request

OWNER = "acme-platform"
REPOSITORY = "invoice-ingest-infra"
PROJECT = "/v1/projects/invoice-ingest"
VAULT = "cloudinfra-vault"
DEV = "cloudinfra-payments-dev"
JORDAN = {"X-Actor": "jordan", "X-Roles": "developer"}
SAM = {"X-Actor": "sam", "X-Roles": "reviewer"}
RESOURCES = [{"id": "uploads", "type": "storage.bucket"}, {"id": "processor", "type": "compute.function"},
             {"id": "orders", "type": "database.table"}, {"id": "jobs", "type": "messaging.queue"}]


def bucket(project_id: str) -> str:
    return f"invoice-ingest-uploads-{hashlib.sha1(project_id.encode()).hexdigest()[:8]}"


@pytest.fixture
def settings(tmp_path):
    return Settings(database_url=TEST_DATABASE_URL, local_state_dir=str(tmp_path), worker_poll_seconds=0,
                    backup_account_id="999999999999", gcp_backup_project=VAULT)


def drain(settings, session_factory) -> None:
    factory = AdapterFactory()
    worker = Worker(session_factory, factory.github(settings), factory.clouds(settings), settings.github_owner,
                    ManifestSigner.from_settings(settings))
    while worker.process_one():
        pass


def provision(client, settings, session_factory, **overrides) -> None:
    client.post("/v1/projects", json=gcp_request(**{"resources": RESOURCES, "connections": [], **overrides}),
                headers={"Idempotency-Key": "k1"})
    drain(settings, session_factory)


@pytest.fixture
def provisioned(client, settings, session_factory) -> None:
    provision(client, settings, session_factory)


def gcp(settings) -> LocalGcp:
    return LocalGcp(settings.local_state_dir)


def vault(settings):
    return gcp(settings).backup(VAULT)


def preview(client, environments=("dev",)) -> dict:
    return client.post(f"{PROJECT}/teardowns:preview",
                       json={"scope": "environment", "environments": list(environments)}).json()


def torn_down(client, settings, session_factory) -> dict:
    teardown = client.post(f"{PROJECT}/teardowns", json={"scope": "environment", "environments": ["dev"],
                                                         "confirmation": "invoice-ingest"}, headers=JORDAN).json()
    client.post(f"{PROJECT}/teardowns/{teardown['id']}/environments/dev:approve", json={"comment": "ok"}, headers=SAM)
    drain(settings, session_factory)
    return client.get(f"{PROJECT}/teardowns/{teardown['id']}").json()


# ---- preview ----

def test_preview_names_the_vault_project(client, provisioned):
    body = preview(client)
    assert (body["backup_account"], body["retention_days"], body["blockers"]) == (VAULT, 60, [])


def test_preview_lists_the_deployments_that_are_deleted(client, provisioned):
    [dev] = preview(client)["environments"]
    assert dev["stacks"] == ["cloudinfra-invoice-ingest-us-east1", "cloudinfra-bootstrap-invoice-ingest"]


def test_preview_lists_the_data_stores_with_their_real_names(client, provisioned):
    [dev] = preview(client)["environments"]
    assert dev["data_stores"] == [
        {"service_id": "uploads", "resource_type": "google_storage_bucket", "physical_name": bucket(DEV),
         "region": "us-east1", "retained": False},
        {"service_id": "orders", "resource_type": "google_firestore_database", "physical_name": "invoice-ingest-orders",
         "region": "us-east1", "retained": True}]


def test_preview_lists_what_is_not_backed_up(client, provisioned):
    [dev] = preview(client)["environments"]
    assert dev["not_backed_up"] == [
        "processor (compute.function): rebuilt from the configuration and the application repository",
        "jobs (messaging.queue): rebuilt from the configuration and the application repository",
        "Pub/Sub messages: transient, not backed up", "Cloud Logging: keep logs with a log sink"]


def test_dual_region_data_is_backed_up_once(client, settings, session_factory):
    provision(client, settings, session_factory, resilience=DR)
    [prod] = preview(client, ("prod",))["environments"]
    assert ([(store["service_id"], store["region"]) for store in prod["data_stores"]], prod["stacks"]) == (
        [("uploads", "us-east1"), ("orders", "us-east1")],
        ["cloudinfra-invoice-ingest-us-east1", "cloudinfra-invoice-ingest-us-east4",
         "cloudinfra-bootstrap-invoice-ingest"])


def test_a_cloud_sql_instance_is_backed_up_in_the_backup_and_dr_vault(client, settings, session_factory):
    database = {"id": "ledger", "type": "google_sql_database_instance",
                "config": {"properties": {"name": "ledger-db", "database_version": "POSTGRES_16",
                                          "settings": {"tier": "db-f1-micro"}}}}
    provision(client, settings, session_factory, resources=[database])
    [dev] = preview(client)["environments"]
    assert dev["data_stores"] == [{"service_id": "ledger", "resource_type": "google_sql_database_instance",
                                   "physical_name": "ledger-db", "region": "us-east1", "retained": False}]


def test_data_the_platform_cannot_back_up_blocks_the_teardown(client, settings, session_factory):
    table = {"id": "events", "type": "google_bigtable_instance", "config": {"properties": {"name": "events"}}}
    provision(client, settings, session_factory, resources=[table])
    assert preview(client)["blockers"] == [
        "Cannot back up events (google_bigtable_instance): the platform has no backup for it yet."]


def test_a_data_store_named_by_an_expression_blocks_the_teardown(client, settings, session_factory):
    database = {"id": "ledger", "type": "google_sql_database_instance",
                "config": {"properties": {"name": "${random_id.ledger.hex}", "database_version": "POSTGRES_16"}}}
    provision(client, settings, session_factory, resources=[database])
    assert preview(client)["blockers"] == [
        "Cannot back up ledger (google_sql_database_instance): its name is not in the configuration."]


def test_a_missing_vault_project_blocks_the_teardown(client, provisioned, session_factory, tmp_path):
    from fastapi.testclient import TestClient

    from app.api.application import ApplicationFactory

    plain = Settings(database_url=TEST_DATABASE_URL, local_state_dir=str(tmp_path), worker_poll_seconds=0,
                     backup_account_id="999999999999")
    other = TestClient(ApplicationFactory(plain, session_factory=session_factory).create())
    body = other.post(f"{PROJECT}/teardowns:preview", json={"scope": "environment", "environments": ["dev"]}).json()
    assert (body["backup_account"], body["blockers"]) == (None, [
        "No vault project is configured: set gcp_backup_project until the Google Cloud landing zone creates one."])


# ---- teardown ----

def test_teardown_backs_up_into_the_locked_bucket_of_the_vault_project(client, settings, session_factory, provisioned):
    teardown = torn_down(client, settings, session_factory)
    points = vault(settings).recovery_points()
    assert (teardown["state"], sorted(point.source_ref for point in points),
            {point.vault for point in points}, {point.locked_until - point.completed_at for point in points},
            all(point.ref.startswith(f"gs://cloudinfra-teardown-us-east1-{VAULT}/") for point in points)) == (
        "completed", [f"projects/_/buckets/{bucket(DEV)}", f"projects/{DEV}/databases/invoice-ingest-orders"],
        {f"cloudinfra-teardown-us-east1-{VAULT}"}, {timedelta(days=60)}, True)


def test_teardown_deletes_the_deployment_then_the_retained_database(client, settings, session_factory, provisioned):
    torn_down(client, settings, session_factory)
    assert [(item["operation"], item["target"]) for item in gcp(settings).operations()] == [
        ("allow_stack_deletion", "invoice-ingest"), ("delete_stack", "invoice-ingest"),
        ("delete_data_store", "google_firestore_database invoice-ingest-orders")]


def test_teardown_removes_workload_identity_and_the_github_environment(client, settings, session_factory,
                                                                       provisioned):
    torn_down(client, settings, session_factory)
    environments = {stack["environment"] for stack in gcp(settings).stacks()}
    with pytest.raises(KeyError):
        LocalGitHub(settings.local_state_dir).environment(OWNER, REPOSITORY, "dev")
    assert environments == {"test", "stage", "prod"}


def test_an_unlocked_vault_bucket_stops_the_teardown_before_anything_is_deleted(client, settings, session_factory,
                                                                                provisioned):
    vault(settings).set_vault_lock("us-east1", locked=False, min_retention_days=0)
    teardown = torn_down(client, settings, session_factory)
    [dev] = teardown["environments"]
    assert (dev["state"], dev["error"], gcp(settings).operations()) == (
        "failed_needs_attention", f"The central vault cloudinfra-teardown-us-east1-{VAULT} is not locked for at least 60 days.", [])


# ---- restore ----

def test_restore_brings_the_data_back_and_imports_it(client, settings, session_factory, provisioned):
    teardown = torn_down(client, settings, session_factory)
    client.post(f"{PROJECT}/teardowns/{teardown['id']}:restore", json={"comment": "ok"}, headers=JORDAN)
    client.post(f"{PROJECT}/teardowns/{teardown['id']}:approve-restore", json={"comment": "ok"}, headers=SAM)
    drain(settings, session_factory)
    imports = [item["target"] for item in gcp(settings).operations() if item["operation"] == "import_stack"]
    assert (sorted(item["physical_name"] for item in vault(settings).restores()), imports,
            client.get(f"{PROJECT}/teardowns/{teardown['id']}").json()["restore"]["state"]) == (
        ["invoice-ingest-orders", bucket(DEV)],
        ["invoice-ingest google_storage_bucket.uploads,google_firestore_database.orders"], "restored")


# ---- Bucket Lock ----

NOW = datetime(2026, 10, 5, tzinfo=UTC)


def locked_point(tmp_path, resource_type="google_storage_bucket"):
    from app.adapters.ports import BackupSource

    backup = LocalGcp(tmp_path).backup(VAULT, clock=lambda: NOW)
    return backup, backup.back_up(BackupSource(DEV, "us-east1", resource_type, "projects/_/buckets/b"))


def test_objects_in_the_locked_bucket_cannot_be_deleted_for_sixty_days(tmp_path):
    from app.adapters.local_backup import RecoveryPointLockedError

    backup, point = locked_point(tmp_path)
    with pytest.raises(RecoveryPointLockedError, match="locked until"):
        backup.delete_recovery_point(point.ref, "group:cloudinfra-backup-super-users", NOW + timedelta(days=59))


def test_after_sixty_days_only_the_super_user_group_may_delete(tmp_path):
    backup, point = locked_point(tmp_path)
    with pytest.raises(PermissionError, match="Only group:cloudinfra-backup-super-users"):
        backup.delete_recovery_point(point.ref, "user:alex@example.com", NOW + timedelta(days=61))


def test_the_super_user_group_deletes_after_sixty_days(tmp_path):
    backup, point = locked_point(tmp_path)
    backup.delete_recovery_point(point.ref, "group:cloudinfra-backup-super-users", NOW + timedelta(days=61))
    assert backup.recovery_points() == []


def test_databases_go_to_the_backup_and_dr_vault(tmp_path):
    _, point = locked_point(tmp_path, "google_sql_database_instance")
    assert (point.vault, point.ref.startswith(
        f"projects/{VAULT}/locations/us-east1/backupVaults/cloudinfra-teardown/dataSources/")) == (
        f"projects/{VAULT}/locations/us-east1/backupVaults/cloudinfra-teardown", True)


# ---- names in the configuration ----

@pytest.mark.parametrize("text, resolved", [
    (None, None),
    ("${substr(sha1(var.unknown), 0, 8)}-x", None),
    ("${var.project_name}-${substr(sha1(var.project_id), 0, 4)}", "demo-" + hashlib.sha1(b"p-1").hexdigest()[:4]),
])
def test_names_resolve_only_from_known_variables(text, resolved):
    from app.providers.gcp.teardown import TerraformNames

    assert TerraformNames({"project_name": "demo", "project_id": "p-1"}).resolve(text) == resolved
