"""The locked teardown vault in Docker (§23, V-2), against the real MinIO container: the store's Object Lock refuses
deletes, and a teardown and restore run on each cloud with `backup_mode=minio`.

Run `docker compose --profile vault up -d vault vault-setup`, then with the environment the README lists:
`uv run pytest tests/integration -m vault --no-cov`. Skipped when no vault answers."""

import os
import time
import urllib.request
import uuid
from datetime import timedelta

import pytest

from app.adapters.local_backup import AwsBackupStyle, RecoveryPointLockedError
from app.adapters.minio_backup import MinioBackup, VaultSetup
from app.adapters.ports import BackupSource
from app.config import Settings
from tests.factories import TEST_DATABASE_URL

ENDPOINT = os.environ.get("VAULT_ENDPOINT", "http://localhost:9000")


def _reachable() -> bool:
    try:
        urllib.request.urlopen(f"{ENDPOINT}/minio/health/live", timeout=2)
    except OSError:
        return False
    return True


pytestmark = [pytest.mark.vault, pytest.mark.skipif(not _reachable(), reason=f"no vault at {ENDPOINT}")]
JORDAN = {"X-Actor": "jordan", "X-Roles": "developer"}
SAM = {"X-Actor": "sam", "X-Roles": "reviewer"}
BACKUP = {"aws": "999999999999", "gcp": "cloudinfra-vault-project", "azure": "5c0ffee0-0000-4000-8000-00000000b4c4"}


def client(user: str, secret: str):
    import boto3
    from botocore.config import Config

    return boto3.client("s3", endpoint_url=ENDPOINT, region_name="us-east-1", aws_access_key_id=user,
                        aws_secret_access_key=secret, config=Config(s3={"addressing_style": "path"}))


def admin():
    return client(os.environ.get("VAULT_ADMIN_ACCESS_KEY", "cloudinfra-admin"),
                  os.environ.get("VAULT_ADMIN_SECRET_KEY", "cloudinfra-admin-secret"))


def platform():
    return client("cloudinfra-platform", os.environ.get("VAULT_PLATFORM_SECRET_KEY", "cloudinfra-platform-secret"))


def super_user():
    return client("cloudinfra-backup-super-users",
                  os.environ.get("VAULT_SUPER_USER_SECRET_KEY", "cloudinfra-super-user-secret"))


@pytest.fixture
def region() -> str:
    """A region of its own per test, so locked objects from other runs don't get in the way."""
    name = f"test-{uuid.uuid4().hex[:12]}"
    VaultSetup(admin()).run({"aws": [name]})
    return name


def vault(**options) -> MinioBackup:
    return MinioBackup(platform(), BACKUP["aws"], "aws", AwsBackupStyle(), **options)


def source(region: str) -> BackupSource:
    return BackupSource("111111111111", region, "AWS::S3::Bucket", f"arn:aws:s3:::uploads-{uuid.uuid4().hex[:6]}")


def test_a_backup_is_locked_by_the_store_for_sixty_days(region):
    point = vault().back_up(source(region))
    stored = vault().recovery_point(point.ref)
    assert (stored.locked_until - stored.completed_at >= timedelta(days=60) - timedelta(seconds=1),
            vault().vault_lock(region).locked) == (True, True)


def test_the_platform_can_neither_delete_nor_bypass(region):
    point = vault().back_up(source(region))
    with pytest.raises(PermissionError):
        vault().delete_recovery_point(point.ref, platform())


def test_compliance_refuses_even_the_super_user_until_the_lock_ends(region):
    locked = vault(retention=timedelta(seconds=3), mode="COMPLIANCE")
    point = locked.back_up(source(region))
    with pytest.raises(RecoveryPointLockedError):
        locked.delete_recovery_point(point.ref, super_user())
    time.sleep(4)
    locked.delete_recovery_point(point.ref, super_user())
    assert locked.recovery_point(point.ref) is None


def test_governance_lets_only_the_super_user_bypass(region):
    point = vault().back_up(source(region))
    vault().delete_recovery_point(point.ref, super_user())
    assert vault().recovery_point(point.ref) is None


def test_a_missing_region_bucket_is_not_locked():
    assert vault().vault_lock(f"none-{uuid.uuid4().hex[:8]}").locked is False


# ---- a teardown and restore on each cloud, through the API ----

@pytest.fixture
def settings(tmp_path):
    return Settings(database_url=TEST_DATABASE_URL, local_state_dir=str(tmp_path), worker_poll_seconds=0,
                    backup_mode="minio", vault_endpoint=ENDPOINT, vault_access_key="cloudinfra-platform",
                    vault_secret_key=os.environ.get("VAULT_PLATFORM_SECRET_KEY", "cloudinfra-platform-secret"),
                    backup_account_id=BACKUP["aws"], gcp_backup_project=BACKUP["gcp"],
                    azure_backup_subscription=BACKUP["azure"])


def drain(settings, session_factory) -> None:
    from app.adapters.factory import AdapterFactory
    from app.provisioning.worker import Worker
    from app.readback.manifest import ManifestSigner

    factory = AdapterFactory()
    worker = Worker(session_factory, factory.github(settings), factory.clouds(settings), settings.github_owner,
                    ManifestSigner.from_settings(settings))
    while worker.process_one():
        pass


def payload(provider: str) -> dict:
    from tests.azure_helpers import azure_request
    from tests.factories import request_dict
    from tests.gcp_helpers import gcp_request

    return {"aws": request_dict, "gcp": gcp_request, "azure": azure_request}[provider]()


@pytest.mark.parametrize("provider, home", [("aws", "us-east-1"), ("gcp", "us-east1"), ("azure", "eastus2")])
def test_a_teardown_backs_up_into_the_locked_store_and_restores_from_it(client, settings, session_factory,
                                                                        provider, home):
    VaultSetup(admin()).run({provider: [home]})
    project = "/v1/projects/invoice-ingest"
    client.post("/v1/projects", json=payload(provider), headers={"Idempotency-Key": "k1"})
    drain(settings, session_factory)
    teardown = client.post(f"{project}/teardowns", json={"scope": "environment", "environments": ["dev"],
                                                         "confirmation": "invoice-ingest"}, headers=JORDAN).json()
    client.post(f"{project}/teardowns/{teardown['id']}/environments/dev:approve", json={"comment": "ok"}, headers=SAM)
    drain(settings, session_factory)
    client.post(f"{project}/teardowns/{teardown['id']}:restore", json={"comment": "ok"}, headers=JORDAN)
    client.post(f"{project}/teardowns/{teardown['id']}:approve-restore", json={"comment": "ok"}, headers=SAM)
    drain(settings, session_factory)
    body = client.get(f"{project}/teardowns/{teardown['id']}").json()
    [dev] = body["environments"]
    stored = MinioBackup(platform(), BACKUP[provider], provider, AwsBackupStyle()).recovery_point(
        dev["recovery_points"][0]["recovery_point_ref"])
    assert (body["state"], body["restore"]["state"], stored.locked_until - stored.completed_at >= timedelta(days=59)) == (
        "completed", "restored", True)
