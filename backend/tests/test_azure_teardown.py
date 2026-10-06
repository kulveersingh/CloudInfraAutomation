"""Teardown and restore on Azure (§22.11.6): data stores from the data template, with their real names (ARM's
uniqueString, computed by the platform); vaulted blob backups and Cosmos DB exports into the locked vault of the
backup subscription; restore with adoption."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.adapters.factory import AdapterFactory
from app.adapters.local_azure import LocalAzure
from app.adapters.local_github import LocalGitHub
from app.config import Settings
from app.providers.azure.expressions import ArmExpressions, unique_string
from app.provisioning.worker import Worker
from app.readback.manifest import ManifestSigner
from tests.azure_helpers import DR, azure_request
from tests.factories import TEST_DATABASE_URL

OWNER = "acme-platform"
REPOSITORY = "invoice-ingest-infra"
PROJECT = "/v1/projects/invoice-ingest"
VAULT = "5c0ffee0-0000-4000-8000-00000000b4c4"
JORDAN = {"X-Actor": "jordan", "X-Roles": "developer"}
SAM = {"X-Actor": "sam", "X-Roles": "reviewer"}
RESOURCES = [{"id": "uploads", "type": "storage.bucket"}, {"id": "processor", "type": "compute.function"},
             {"id": "orders", "type": "database.table"}, {"id": "jobs", "type": "messaging.queue"}]
BACKUP_GROUP = f"/subscriptions/{VAULT}/resourceGroups/rg-cloudinfra-backup/providers"
BLOB_VAULT = f"{BACKUP_GROUP}/Microsoft.DataProtection/backupVaults/bv-teardown-eastus2"


def subscription(environment: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"cloudinfra:azure:pf-payments:{environment}"))


def group(environment: str) -> str:
    return f"/subscriptions/{subscription(environment)}/resourceGroups/rg-invoice-ingest-{environment}"


def account(environment: str = "dev") -> str:
    return f"stuploads{unique_string(group(environment))}"


def cosmos(environment: str = "dev") -> str:
    return f"cosmos-invoice-ingest-orders-{unique_string(group(environment))}"


@pytest.fixture
def settings(tmp_path):
    return Settings(database_url=TEST_DATABASE_URL, local_state_dir=str(tmp_path), worker_poll_seconds=0,
                    backup_account_id="999999999999", azure_backup_subscription=VAULT)


def drain(settings, session_factory) -> None:
    factory = AdapterFactory()
    worker = Worker(session_factory, factory.github(settings), factory.clouds(settings), settings.github_owner,
                    ManifestSigner.from_settings(settings))
    while worker.process_one():
        pass


def provision(client, settings, session_factory, **overrides) -> None:
    client.post("/v1/projects", json=azure_request(**{"resources": RESOURCES, "connections": [], **overrides}),
                headers={"Idempotency-Key": "k1"})
    drain(settings, session_factory)


@pytest.fixture
def provisioned(client, settings, session_factory) -> None:
    provision(client, settings, session_factory)


def azure(settings) -> LocalAzure:
    return LocalAzure(settings.local_state_dir)


def vault(settings):
    return azure(settings).backup(VAULT)


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

def test_preview_names_the_backup_subscription(client, provisioned):
    body = preview(client)
    assert (body["backup_account"], body["retention_days"], body["blockers"]) == (VAULT, 60, [])


def test_preview_lists_the_stacks_in_delete_order(client, provisioned):
    [dev] = preview(client)["environments"]
    assert dev["stacks"] == ["invoice-ingest-eastus2", "invoice-ingest-shared", "invoice-ingest-data",
                             "cloudinfra-bootstrap-invoice-ingest"]


def test_preview_lists_the_data_stores_with_their_real_names(client, provisioned):
    [dev] = preview(client)["environments"]
    assert dev["data_stores"] == [
        {"service_id": "uploads", "resource_type": "Microsoft.Storage/storageAccounts", "physical_name": account(),
         "region": "eastus2", "retained": False},
        {"service_id": "orders", "resource_type": "Microsoft.DocumentDB/databaseAccounts", "physical_name": cosmos(),
         "region": "eastus2", "retained": False}]


def test_preview_lists_what_is_not_backed_up(client, provisioned):
    [dev] = preview(client)["environments"]
    assert dev["not_backed_up"] == [
        "processor (compute.function): rebuilt from the templates and the application repository",
        "jobs (messaging.queue): rebuilt from the templates and the application repository",
        "Service Bus messages: transient, not backed up", "Logs: keep them with diagnostic settings",
        "The contract Key Vault: soft-deleted for 90 days, and recovered by the next deployment"]


def test_multi_region_data_is_backed_up_once_in_the_primary_region(client, settings, session_factory):
    provision(client, settings, session_factory, resilience=DR)
    [prod] = preview(client, ("prod",))["environments"]
    assert ([(store["service_id"], store["region"]) for store in prod["data_stores"]], prod["stacks"]) == (
        [("uploads", "eastus2"), ("orders", "eastus2")],
        ["invoice-ingest-eastus2", "invoice-ingest-centralus", "invoice-ingest-shared", "invoice-ingest-data",
         "cloudinfra-bootstrap-invoice-ingest"])


def test_a_tier_2_type_without_data_is_rebuilt(client, settings, session_factory):
    provision(client, settings, session_factory, resources=[{"id": "cache", "type": "Microsoft.Cache/redis",
                                                             "config": {}}])
    [dev] = preview(client)["environments"]
    assert (dev["data_stores"], dev["not_backed_up"][0]) == (
        [], "cache (Microsoft.Cache/redis): rebuilt from the templates and the application repository")


def test_data_the_platform_cannot_back_up_blocks_the_teardown(client, settings, session_factory):
    provision(client, settings, session_factory, resources=[{"id": "ledger", "type": "Microsoft.Sql/servers",
                                                             "config": {}}])
    assert preview(client)["blockers"] == [
        "Cannot back up ledger (Microsoft.Sql/servers): the platform has no backup for it yet."]


def test_a_missing_backup_subscription_blocks_the_teardown(client, provisioned, session_factory, tmp_path):
    from fastapi.testclient import TestClient

    from app.api.application import ApplicationFactory

    plain = Settings(database_url=TEST_DATABASE_URL, local_state_dir=str(tmp_path), worker_poll_seconds=0,
                     backup_account_id="999999999999")
    other = TestClient(ApplicationFactory(plain, session_factory=session_factory).create())
    body = other.post(f"{PROJECT}/teardowns:preview", json={"scope": "environment", "environments": ["dev"]}).json()
    assert (body["backup_account"], body["blockers"]) == (None, [
        ("No backup subscription is configured: set azure_backup_subscription until the Azure landing zone creates "
         "one.")])


# ---- teardown ----

def test_teardown_backs_up_blobs_into_the_locked_vault_and_exports_cosmos(client, settings, session_factory,
                                                                         provisioned):
    teardown = torn_down(client, settings, session_factory)
    points = {point.resource_type: point for point in vault(settings).recovery_points()}
    blobs, export = points["Microsoft.Storage/storageAccounts"], points["Microsoft.DocumentDB/databaseAccounts"]
    assert (teardown["state"], blobs.source_ref, blobs.vault, export.source_ref, export.vault.endswith(
        "/containers/cloudinfra-teardown"), {point.locked_until - point.completed_at for point in points.values()}) == (
        "completed", f"{group('dev')}/providers/Microsoft.Storage/storageAccounts/{account()}", BLOB_VAULT,
        f"{group('dev')}/providers/Microsoft.DocumentDB/databaseAccounts/{cosmos()}", True, {timedelta(days=60)})


def test_teardown_deletes_the_stacks_and_leaves_no_data_store_behind(client, settings, session_factory, provisioned):
    torn_down(client, settings, session_factory)
    assert [(item["operation"], item["target"]) for item in azure(settings).operations()] == [
        ("allow_stack_deletion", "invoice-ingest"), ("delete_stack", "invoice-ingest")]


def test_teardown_removes_the_deploy_identity_and_the_github_environment(client, settings, session_factory,
                                                                         provisioned):
    torn_down(client, settings, session_factory)
    environments = {stack["environment"] for stack in azure(settings).stacks()}
    with pytest.raises(KeyError):
        LocalGitHub(settings.local_state_dir).environment(OWNER, REPOSITORY, "dev")
    assert environments == {"test", "stage", "prod"}


def test_an_unlocked_vault_stops_the_teardown_before_anything_is_deleted(client, settings, session_factory,
                                                                         provisioned):
    vault(settings).set_vault_lock("eastus2", locked=False, min_retention_days=0)
    [dev] = torn_down(client, settings, session_factory)["environments"]
    assert (dev["state"], dev["error"], azure(settings).operations()) == (
        "failed_needs_attention", f"The central vault {BLOB_VAULT} is not locked for at least 60 days.", [])


# ---- restore ----

def test_restore_brings_the_data_back_under_its_names_and_adopts_it(client, settings, session_factory, provisioned):
    teardown = torn_down(client, settings, session_factory)
    client.post(f"{PROJECT}/teardowns/{teardown['id']}:restore", json={"comment": "ok"}, headers=JORDAN)
    client.post(f"{PROJECT}/teardowns/{teardown['id']}:approve-restore", json={"comment": "ok"}, headers=SAM)
    drain(settings, session_factory)
    imports = [item["target"] for item in azure(settings).operations() if item["operation"] == "import_stack"]
    assert (sorted(item["physical_name"] for item in vault(settings).restores()), imports,
            client.get(f"{PROJECT}/teardowns/{teardown['id']}").json()["restore"]["state"]) == (
        sorted([account(), cosmos()]),
        [(f"invoice-ingest Microsoft.Storage/storageAccounts/{account()},"
          f"Microsoft.DocumentDB/databaseAccounts/{cosmos()}")], "restored")


# ---- the locked vault ----

NOW = datetime(2026, 10, 6, tzinfo=UTC)


def test_after_sixty_days_only_the_super_user_group_may_delete(tmp_path):
    from app.adapters.ports import BackupSource

    backup = LocalAzure(tmp_path).backup(VAULT, clock=lambda: NOW)
    point = backup.back_up(BackupSource(subscription("dev"), "eastus2", "Microsoft.Storage/storageAccounts", "x"))
    with pytest.raises(PermissionError, match="Only group:cloudinfra-backup-super-users"):
        backup.delete_recovery_point(point.ref, "user:alex@example.com", NOW + timedelta(days=61))


# ---- names: ARM expressions, evaluated by the platform ----

@pytest.mark.parametrize("parts, expected", [  # each value checked against Bicep CLI 0.48.1 (`bicep console`)
    (("abc",), "cgtzqvhu4i23s"),
    (("/subscriptions/f27c2614-6558-5b71-a7d0-35feaa9a9e01/resourceGroups/rg-invoice-ingest-prod",), "os4tnuguwk72e"),
    (("a",), "eveiun73364hy"),
    (("ab",), "twldla3s3qb3q"),
    (("abcdefg",), "logmp4qgzfm46"),
    (("abcdefgh",), "q7ncvd5x2rx4e"),
    (("abcdefghi",), "zignisl6otg3u"),
    (("abcdefghijklm",), "drrqz7xt5wi54"),
    (("/subscriptions/x/resourceGroups/rg-a", "eastus2"), "vahbmjcrjob36"),
    (("déjà vu",), "sjpsqt4vlgjwo"),
])
def test_unique_string_matches_azure_resource_manager(parts, expected):
    assert unique_string(*parts) == expected


EXPRESSIONS = ArmExpressions(parameters={"projectName": "demo", "location": "eastus2"},
                             variables={"plain": "kept", "nested": "[concat('n-', parameters('projectName'))]"},
                             resource_group_id="/subscriptions/x/resourceGroups/rg-a")


@pytest.mark.parametrize("text, value", [
    ("literal-name", "literal-name"),
    ("[concat('st', take('uploads-archive', 9), uniqueString(resourceGroup().id))]",
     "stuploads-a" + unique_string("/subscriptions/x/resourceGroups/rg-a")),
    ("[uniqueString(resourceGroup().id, parameters('location'))]", "vahbmjcrjob36"),
    ("[format('{0}/{1}', parameters('projectName'), 'it''s')]", "demo/it's"),
    ("[variables('plain')]", "kept"),
    ("[variables('nested')]", "n-demo"),
    ("[[not an expression]", "[not an expression]"),
    ("[newGuid()]", None),
    ("[parameters('unknown')]", None),
    ("[variables('unknown')]", None),
    ("[resourceGroup().location]", None),
    ("[concat('a', 1)]", None),
    ("[toLower('ABC')]", "abc"),
    ("[]", None),
    ("[concat('a') + 'b']", None),
    ("[concat('a']", None),
    ("[concat('a'", "[concat('a'"),
    ("['a' 'b']", None),
    ("[take('abc', 'x')]", None),
    ("[parameters('projectName').id]", None),
    ("[resourceGroup()]", None),
    ("[resourceGroup().]", None),
    ("[projectName]", None),
    (None, None),
])
def test_names_resolve_only_from_what_the_platform_knows(text, value):
    assert EXPRESSIONS.evaluate(text) == value


def test_a_data_store_whose_name_cannot_be_resolved_blocks_the_teardown():
    from app.providers.azure.teardown import AzureInventory
    from app.synth.request import ProjectRequest

    class Unnamed:
        def synthesize(self, request):
            return {"data": {"variables": {}, "resources": [
                {"type": "Microsoft.Storage/storageAccounts", "comments": "uploads", "name": "[newGuid()]"}]}}

    request = ProjectRequest.model_validate(azure_request(resources=[{"id": "uploads", "type": "storage.bucket"}]))
    stores, problems = AzureInventory(Unnamed()).for_environment(request, "dev", subscription("dev"), ["eastus2"])
    assert (stores, problems) == ([], [
        "Cannot back up uploads (Microsoft.Storage/storageAccounts): its name is not in the template."])
