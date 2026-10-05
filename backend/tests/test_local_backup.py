from datetime import UTC, datetime, timedelta

import pytest

from app.adapters.local_backup import LocalBackup, RecoveryPointLockedError
from app.adapters.ports import BackupSource

BACKUP_ACCOUNT = "999999999999"
NOW = datetime(2026, 10, 4, 12, 0, tzinfo=UTC)
SOURCE = BackupSource(account_id="222222222222", region="us-east-1", resource_type="AWS::S3::Bucket",
                      source_ref="arn:aws:s3:::demo--uploads-222222222222-us-east-1")


@pytest.fixture
def backup(tmp_path) -> LocalBackup:
    return LocalBackup(tmp_path, BACKUP_ACCOUNT, clock=lambda: NOW)


def test_backup_lands_in_the_central_vault_of_the_same_region(backup):
    point = backup.back_up(SOURCE)
    assert (point.vault, point.account_id, point.region, point.ref.startswith(
        "arn:aws:backup:us-east-1:999999999999:recovery-point:")) == (
        "cloudinfra-teardown-us-east-1", BACKUP_ACCOUNT, "us-east-1", True)


def test_backup_is_complete_and_locked_for_sixty_days(backup):
    point = backup.back_up(SOURCE)
    assert (point.completed_at, point.locked_until) == (NOW, NOW + timedelta(days=60))


def test_recovery_point_can_be_looked_up(backup):
    point = backup.back_up(SOURCE)
    assert backup.recovery_point(point.ref) == point


def test_unknown_recovery_point(backup):
    assert backup.recovery_point("arn:aws:backup:us-east-1:999999999999:recovery-point:nope") is None


def test_central_vaults_are_locked_by_default(backup):
    lock = backup.vault_lock("us-east-2")
    assert (lock.locked, lock.min_retention_days) == (True, 60)


def test_vault_lock_can_be_changed_to_simulate_a_missing_lock(backup):
    backup.set_vault_lock("us-east-1", locked=False, min_retention_days=0)
    assert backup.vault_lock("us-east-1").locked is False


def test_failed_backups_raise(backup):
    backup.fail_backups_of(SOURCE.source_ref)
    with pytest.raises(RuntimeError, match="Backup of"):
        backup.back_up(SOURCE)


def test_nobody_can_delete_a_recovery_point_within_sixty_days(backup):
    point = backup.back_up(SOURCE)
    with pytest.raises(RecoveryPointLockedError, match="locked until"):
        backup.delete_recovery_point(point.ref, role="CloudInfraBackupSuperUser", at=NOW + timedelta(days=59))


def test_only_super_users_can_delete_after_sixty_days(backup):
    point = backup.back_up(SOURCE)
    with pytest.raises(PermissionError, match="CloudInfraBackupSuperUser"):
        backup.delete_recovery_point(point.ref, role="PlatformReleaseExecutor", at=NOW + timedelta(days=61))


def test_super_user_deletes_after_sixty_days(backup):
    point = backup.back_up(SOURCE)
    backup.delete_recovery_point(point.ref, role="CloudInfraBackupSuperUser", at=NOW + timedelta(days=60))
    assert backup.recovery_point(point.ref) is None


def test_restore_records_the_target(backup):
    point = backup.back_up(SOURCE)
    backup.restore(point.ref, account_id="222222222222", region="us-east-1", physical_name="demo--uploads")
    assert backup.restores() == [{"recovery_point": point.ref, "account": "222222222222", "region": "us-east-1",
                                  "physical_name": "demo--uploads", "resource_type": "AWS::S3::Bucket"}]


def test_restore_of_a_deleted_recovery_point_fails(backup):
    point = backup.back_up(SOURCE)
    backup.delete_recovery_point(point.ref, role="CloudInfraBackupSuperUser", at=NOW + timedelta(days=60))
    with pytest.raises(KeyError):
        backup.restore(point.ref, account_id="222222222222", region="us-east-1", physical_name="demo--uploads")


def test_cleared_failures_back_up_again(backup):
    backup.fail_backups_of(SOURCE.source_ref)
    backup.clear_failures()
    assert backup.back_up(SOURCE).source_ref == SOURCE.source_ref
