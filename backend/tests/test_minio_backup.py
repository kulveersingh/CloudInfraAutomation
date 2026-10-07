"""The locked teardown vault in Docker (§23, V-1): `MinioBackup` behind the backup port, against an in-memory S3 that
enforces Object Lock as MinIO does, and its selection with `backup_mode`."""

import hashlib
from datetime import UTC, datetime, timedelta

import pytest

from app.adapters.local_aws import LocalAws
from app.adapters.local_azure import AzureBackupStyle, LocalAzure
from app.adapters.local_backup import AwsBackupStyle, LocalBackup, RecoveryPointLockedError
from app.adapters.minio_backup import CONTROL_BUCKET, MinioBackup, MinioVault, bucket_name
from app.adapters.ports import BackupSource
from app.config import Settings
from tests.factories import TEST_DATABASE_URL
from tests.fake_s3 import ALL, FakeS3, FakeStore

NOW = datetime(2026, 10, 6, tzinfo=UTC)
ACCOUNT = "999999999999"
SOURCE = BackupSource("111111111111", "us-east-1", "AWS::S3::Bucket", "arn:aws:s3:::invoice-ingest-uploads")
SIXTY_DAYS = {"ObjectLockEnabled": "Enabled", "Rule": {"DefaultRetention": {"Mode": "GOVERNANCE", "Days": 60}}}


class Clock:
    def __init__(self):
        self.now = NOW

    def __call__(self):
        return self.now


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def store(clock):
    store = FakeStore(clock)
    admin = FakeS3(store, ALL, bypass=True)
    for region in ("us-east-1", "us-east-2"):
        admin.create_bucket(Bucket=bucket_name("aws", region), ObjectLockEnabledForBucket=True)
        admin.put_object_lock_configuration(Bucket=bucket_name("aws", region), ObjectLockConfiguration=SIXTY_DAYS)
    admin.create_bucket(Bucket=CONTROL_BUCKET)
    return store


def platform(store) -> FakeS3:
    """What the platform's identity may do: no deletes in the vault buckets, no bypass (V-6)."""
    return FakeS3(store, frozenset({CONTROL_BUCKET}))


def super_user(store) -> FakeS3:
    return FakeS3(store, ALL, bypass=True)


def backup(store, clock, **options) -> MinioBackup:
    return MinioBackup(platform(store), ACCOUNT, "aws", AwsBackupStyle(), clock, **options)


# ---- backing up into the locked store ----

def test_a_backup_is_an_object_locked_for_sixty_days_in_its_regions_bucket(store, clock):
    point = backup(store, clock).back_up(SOURCE)
    [version] = store.buckets["teardown-aws-us-east-1"]["objects"][hashlib.sha256(point.ref.encode()).hexdigest()]
    assert (point.ref.startswith(f"arn:aws:backup:us-east-1:{ACCOUNT}:recovery-point:"), point.vault,
            point.locked_until - point.completed_at, version["ObjectLockMode"], version["Metadata"]["ref"]) == (
        True, "cloudinfra-teardown-us-east-1", timedelta(days=60), "GOVERNANCE", point.ref)


def test_a_recovery_point_reads_its_lock_from_the_store(store, clock):
    vault = backup(store, clock)
    point = vault.back_up(SOURCE)
    assert vault.recovery_point(point.ref) == point


def test_the_lock_read_back_is_the_whole_retention_although_the_store_keeps_seconds(store, clock):
    """Otherwise the teardown's check (locked_until - completed_at >= 60 days) fails by a fraction of a second."""
    clock.now = NOW + timedelta(microseconds=345678)
    vault = backup(store, clock)
    stored = vault.recovery_point(vault.back_up(SOURCE).ref)
    assert stored.locked_until - stored.completed_at == timedelta(days=60)


def test_an_unknown_recovery_point_is_none(store, clock):
    assert backup(store, clock).recovery_point("arn:aws:backup:us-east-1:1:recovery-point:none") is None


def test_backing_up_into_a_region_without_a_bucket_fails(store, clock):
    with pytest.raises(RuntimeError, match="teardown-aws-eu-west-1"):
        backup(store, clock).back_up(BackupSource("1", "eu-west-1", "AWS::S3::Bucket", "arn:aws:s3:::other"))


def test_compliance_mode_is_a_setting(store, clock):
    point = backup(store, clock, mode="COMPLIANCE").back_up(SOURCE)
    key = hashlib.sha256(point.ref.encode()).hexdigest()
    assert store.buckets["teardown-aws-us-east-1"]["objects"][key][0]["ObjectLockMode"] == "COMPLIANCE"


def test_each_cloud_keeps_its_own_names(store, clock):
    admin = FakeS3(store, ALL, bypass=True)
    admin.create_bucket(Bucket=bucket_name("azure", "eastus2"), ObjectLockEnabledForBucket=True)
    vault = MinioBackup(platform(store), "5c0ffee0-0000-4000-8000-00000000b4c4", "azure", AzureBackupStyle(), clock)
    point = vault.back_up(BackupSource("sub", "eastus2", "Microsoft.Storage/storageAccounts", "/subscriptions/sub/x"))
    assert point.vault.endswith("/backupVaults/bv-teardown-eastus2")


# ---- the lock is the store's ----

def test_the_platform_cannot_delete_a_backup(store, clock):
    point = backup(store, clock).back_up(SOURCE)
    with pytest.raises(PermissionError, match="Access Denied"):
        backup(store, clock).delete_recovery_point(point.ref, platform(store))


def test_the_super_user_cannot_delete_before_the_lock_ends(store, clock):
    vault = backup(store, clock, retention=timedelta(seconds=3), mode="COMPLIANCE")
    point = vault.back_up(SOURCE)
    with pytest.raises(RecoveryPointLockedError, match="WORM protected"):
        vault.delete_recovery_point(point.ref, super_user(store))


def test_the_super_user_deletes_after_the_lock(store, clock):
    vault = backup(store, clock, retention=timedelta(seconds=3))
    point = vault.back_up(SOURCE)
    clock.now = NOW + timedelta(seconds=4)
    vault.delete_recovery_point(point.ref, super_user(store))
    assert vault.recovery_point(point.ref) is None


def test_governance_lets_the_super_user_bypass_the_lock(store, clock):
    vault = backup(store, clock)
    point = vault.back_up(SOURCE)
    vault.delete_recovery_point(point.ref, super_user(store))
    assert vault.recovery_point(point.ref) is None


def test_deleting_an_unknown_recovery_point_is_a_key_error(store, clock):
    with pytest.raises(KeyError):
        backup(store, clock).delete_recovery_point("arn:none", super_user(store))


# ---- the vault check ----

def test_a_bucket_with_sixty_days_default_retention_is_locked(store, clock):
    lock = backup(store, clock).vault_lock("us-east-1")
    assert (lock.locked, lock.min_retention_days) == (True, 60)


@pytest.mark.parametrize("configuration, days", [
    ({"ObjectLockEnabled": "Enabled"}, 0),
    ({"ObjectLockEnabled": "Enabled", "Rule": {"DefaultRetention": {"Mode": "GOVERNANCE", "Days": 30}}}, 30),
    ({"ObjectLockEnabled": "Enabled", "Rule": {"DefaultRetention": {"Mode": "COMPLIANCE", "Years": 1}}}, 365),
])
def test_retention_is_read_from_the_bucket(store, clock, configuration, days):
    FakeS3(store, ALL, bypass=True).put_object_lock_configuration(Bucket="teardown-aws-us-east-1",
                                                                  ObjectLockConfiguration=configuration)
    lock = backup(store, clock).vault_lock("us-east-1")
    assert (lock.locked, lock.min_retention_days) == (days >= 60, days)


def test_a_bucket_without_object_lock_is_not_locked(store, clock):
    FakeS3(store, ALL, bypass=True).create_bucket(Bucket="teardown-aws-eu-west-1")
    assert backup(store, clock).vault_lock("eu-west-1").locked is False


def test_a_missing_bucket_is_not_locked(store, clock):
    lock = backup(store, clock).vault_lock("ap-south-1")
    assert (lock.locked, lock.min_retention_days) == (False, 0)


def test_other_store_errors_are_raised(store, clock):
    class Broken(FakeS3):
        def get_object_lock_configuration(self, Bucket):
            from tests.fake_s3 import error
            raise error("InternalError", "boom")

    with pytest.raises(Exception, match="boom"):
        MinioBackup(Broken(store), ACCOUNT, "aws", AwsBackupStyle(), clock).vault_lock("us-east-1")


def test_other_errors_writing_a_backup_are_raised(store, clock):
    from tests.fake_s3 import error

    class Full(FakeS3):
        def put_object(self, Bucket, Key, Body, **options):
            if Bucket.startswith("teardown-"):
                raise error("XMinioStorageFull", "Storage backend has reached its minimum free drive threshold.")
            return super().put_object(Bucket, Key, Body, **options)

    with pytest.raises(Exception, match="minimum free drive"):
        MinioBackup(Full(store), ACCOUNT, "aws", AwsBackupStyle(), clock).back_up(SOURCE)


def test_other_errors_reading_are_raised(store, clock):
    from tests.fake_s3 import error

    class Denied(FakeS3):
        def get_object(self, Bucket, Key):
            raise error("AccessDenied", "Access Denied.")

    with pytest.raises(Exception, match="Access Denied"):
        MinioBackup(Denied(store), ACCOUNT, "aws", AwsBackupStyle(), clock).recovery_point("arn:x")


# ---- restores and injected failures ----

def test_a_restore_reads_the_backup_and_is_recorded(store, clock):
    vault = backup(store, clock)
    point = vault.back_up(SOURCE)
    vault.restore(point.ref, "222222222222", "us-east-1", "invoice-ingest-uploads")
    assert vault.restores() == [{"recovery_point": point.ref, "account": "222222222222", "region": "us-east-1",
                                 "physical_name": "invoice-ingest-uploads", "resource_type": "AWS::S3::Bucket"}]


def test_restoring_an_unknown_recovery_point_fails(store, clock):
    with pytest.raises(KeyError, match="does not exist"):
        backup(store, clock).restore("arn:none", "1", "us-east-1", "x")


def test_no_restores_yet(store, clock):
    assert backup(store, clock).restores() == []


def test_injected_failures_fail_backups_until_cleared(store, clock):
    vault = backup(store, clock)
    vault.fail_backups_of(SOURCE.source_ref)
    with pytest.raises(RuntimeError, match="failed"):
        vault.back_up(SOURCE)
    vault.clear_failures()
    assert vault.back_up(SOURCE).source_ref == SOURCE.source_ref


# ---- selection ----

def settings(tmp_path, **overrides) -> Settings:
    return Settings(database_url=TEST_DATABASE_URL, local_state_dir=str(tmp_path), **overrides)


def test_local_mode_keeps_the_json_vault(tmp_path):
    assert isinstance(LocalAws.from_settings(settings(tmp_path)).backup(ACCOUNT), LocalBackup)


def test_minio_mode_backs_every_local_cloud_with_the_locked_store(tmp_path):
    chosen = settings(tmp_path, backup_mode="minio", vault_secret_key="platform-secret", vault_retention_days=7)
    aws, azure = LocalAws.from_settings(chosen).backup(ACCOUNT), LocalAzure.from_settings(chosen).backup("sub")
    assert (isinstance(aws, MinioBackup), isinstance(azure, MinioBackup), aws.retention, aws.provider,
            azure.provider) == (True, True, timedelta(days=7), "aws", "azure")


def test_the_vault_client_points_at_the_configured_endpoint(tmp_path):
    vault = MinioVault.from_settings(settings(tmp_path, backup_mode="minio", vault_endpoint="http://vault:9000",
                                              vault_secret_key="platform-secret"))
    assert (vault.client.meta.endpoint_url, vault.mode, vault.retention) == (
        "http://vault:9000", "GOVERNANCE", timedelta(days=60))


def test_an_unknown_backup_mode_is_refused(tmp_path):
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        settings(tmp_path, backup_mode="tape")


# ---- setup: the control bucket and a locked bucket per region (V-2) ----

def admin_of(store) -> FakeS3:
    return FakeS3(store, ALL, bypass=True)


def test_setup_creates_the_control_bucket_and_a_locked_bucket_per_region(clock):
    from app.adapters.minio_backup import VaultSetup

    store = FakeStore(clock)
    created = VaultSetup(admin_of(store)).run({"aws": ["us-east-1"], "gcp": ["us-east1"]})
    assert (created, store.buckets["teardown-gcp-us-east1"]["lock"], store.buckets[CONTROL_BUCKET]["lock"]) == (
        [CONTROL_BUCKET, "teardown-aws-us-east-1", "teardown-gcp-us-east1"], SIXTY_DAYS, None)


def test_running_the_setup_again_is_safe(clock):
    from app.adapters.minio_backup import VaultSetup

    store = FakeStore(clock)
    VaultSetup(admin_of(store)).run({"aws": ["us-east-1"]})
    assert VaultSetup(admin_of(store)).run({"aws": ["us-east-1"]}) == [CONTROL_BUCKET, "teardown-aws-us-east-1"]


def test_the_setup_takes_the_mode_and_days(clock):
    from app.adapters.minio_backup import VaultSetup

    store = FakeStore(clock)
    VaultSetup(admin_of(store), mode="COMPLIANCE", days=90).run({"azure": ["eastus2"]})
    assert store.buckets["teardown-azure-eastus2"]["lock"]["Rule"] == {
        "DefaultRetention": {"Mode": "COMPLIANCE", "Days": 90}}


def test_other_setup_errors_are_raised(clock):
    from app.adapters.minio_backup import VaultSetup
    from tests.fake_s3 import error

    class Refusing(FakeS3):
        def create_bucket(self, Bucket, ObjectLockEnabledForBucket=False):
            raise error("AccessDenied", "Access Denied.")

    with pytest.raises(Exception, match="Access Denied"):
        VaultSetup(Refusing(FakeStore(clock))).run({"aws": ["us-east-1"]})


def test_the_setup_command_covers_every_enabled_region_in_the_registry(session, clock):
    from app.adapters.minio_backup import VaultSetupCommand
    from app.seed import ReferenceDataSeeder

    ReferenceDataSeeder(session).seed()
    session.commit()
    store = FakeStore(clock)
    VaultSetupCommand(settings_for_database(), admin_of(store)).run()
    assert ("teardown-azure-eastus2" in store.buckets, "teardown-gcp-us-east1" in store.buckets,
            "teardown-aws-us-east-1" in store.buckets, "teardown-azure-swedencentral" in store.buckets) == (
        True, True, True, False)


def settings_for_database() -> Settings:
    return Settings(database_url=TEST_DATABASE_URL, vault_retention_days=60)


def test_the_setup_command_signs_in_as_the_admin_from_the_environment(monkeypatch):
    from app.adapters.minio_backup import VaultSetupCommand

    monkeypatch.setenv("VAULT_ADMIN_ACCESS_KEY", "admin")
    monkeypatch.setenv("VAULT_ADMIN_SECRET_KEY", "admin-secret")
    command = VaultSetupCommand.from_environment(Settings(vault_endpoint="http://vault:9000"))
    assert (command.client.meta.endpoint_url, command.client._request_signer._credentials.access_key) == (
        "http://vault:9000", "admin")

