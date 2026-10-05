import json
import uuid
from abc import ABC, abstractmethod
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.adapters.ports import BackupPort, BackupSource, RecoveryPoint, VaultLock

STATE_FILE = "backup.json"
CENTRAL_VAULT = "cloudinfra-teardown-{region}"
RETENTION_DAYS = 60
SUPER_USER_ROLE = "CloudInfraBackupSuperUser"


class BackupStyle(ABC):
    """How a cloud names its locked central vault, its recovery points, and who may delete them after the lock."""

    super_user: str

    @abstractmethod
    def vault(self, backup_account_id: str, region: str, resource_type: str) -> str:
        ...

    @abstractmethod
    def ref(self, backup_account_id: str, region: str, resource_type: str) -> str:
        ...


class AwsBackupStyle(BackupStyle):
    """AWS Backup: a central vault per region with Vault Lock in compliance mode."""

    super_user = SUPER_USER_ROLE

    def vault(self, backup_account_id, region, resource_type):
        return CENTRAL_VAULT.format(region=region)

    def ref(self, backup_account_id, region, resource_type):
        return f"arn:aws:backup:{region}:{backup_account_id}:recovery-point:{uuid.uuid4()}"


class RecoveryPointLockedError(Exception):
    """Vault Lock in compliance mode: nobody can delete a recovery point before its minimum retention."""


class LocalBackup(BackupPort):
    """AWS Backup stand-in: backups complete at once, and the central vault's lock is enforced as in AWS (§21.9.1).

    `delete_recovery_point` exists only here, to test the lock the way a super user meets it in the console; the
    platform's port has no deletion."""

    def __init__(self, root, backup_account_id: str, clock: Callable[[], datetime] | None = None,
                 provider: str = "aws", style: BackupStyle | None = None):
        self._state_file = Path(root) / provider / STATE_FILE
        self._account = backup_account_id
        self._clock = clock or (lambda: datetime.now(UTC))
        self._style = style or AwsBackupStyle()

    def back_up(self, source: BackupSource) -> RecoveryPoint:
        state = self._read()
        if source.source_ref in state["failing"]:
            raise RuntimeError(f"Backup of {source.source_ref} failed.")
        completed = self._clock()
        point = RecoveryPoint(
            ref=self._style.ref(self._account, source.region, source.resource_type),
            vault=self._style.vault(self._account, source.region, source.resource_type), account_id=self._account,
            region=source.region,
            source_ref=source.source_ref, resource_type=source.resource_type, completed_at=completed,
            locked_until=completed + timedelta(days=RETENTION_DAYS))
        state["recovery_points"].append(_point_json(point))
        self._write(state)
        return point

    def vault_lock(self, region: str) -> VaultLock:
        lock = self._read()["locks"].get(region, {"locked": True, "min_retention_days": RETENTION_DAYS})
        return VaultLock(locked=lock["locked"], min_retention_days=lock["min_retention_days"])

    def recovery_point(self, ref: str) -> RecoveryPoint | None:
        return next((point for point in self.recovery_points() if point.ref == ref), None)

    def restore(self, recovery_point_ref: str, account_id: str, region: str, physical_name: str) -> None:
        point = self.recovery_point(recovery_point_ref)
        if point is None:
            raise KeyError(f"Recovery point {recovery_point_ref} does not exist.")
        state = self._read()
        state["restores"].append({"recovery_point": point.ref, "account": account_id, "region": region,
                                  "physical_name": physical_name, "resource_type": point.resource_type})
        self._write(state)

    # ---- local helpers: inspection, failure injection and the super user's console ----

    def recovery_points(self) -> list[RecoveryPoint]:
        return [_point(item) for item in self._read()["recovery_points"]]

    def restores(self) -> list[dict]:
        return self._read()["restores"]

    def fail_backups_of(self, source_ref: str) -> None:
        state = self._read()
        state["failing"].append(source_ref)
        self._write(state)

    def clear_failures(self) -> None:
        state = self._read()
        state["failing"] = []
        self._write(state)

    def set_vault_lock(self, region: str, locked: bool, min_retention_days: int) -> None:
        state = self._read()
        state["locks"][region] = {"locked": locked, "min_retention_days": min_retention_days}
        self._write(state)

    def delete_recovery_point(self, ref: str, role: str, at: datetime) -> None:
        point = self.recovery_point(ref)
        if at < point.locked_until:
            raise RecoveryPointLockedError(f"{ref} is locked until {point.locked_until.isoformat()}.")
        if role != self._style.super_user:
            raise PermissionError(f"Only {self._style.super_user} can delete recovery points.")
        state = self._read()
        state["recovery_points"] = [item for item in state["recovery_points"] if item["ref"] != ref]
        self._write(state)

    def _read(self) -> dict:
        if not self._state_file.exists():
            return {"recovery_points": [], "failing": [], "locks": {}, "restores": []}
        return json.loads(self._state_file.read_text())

    def _write(self, state: dict) -> None:
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        self._state_file.write_text(json.dumps(state, indent=2, sort_keys=True))


def _point_json(point: RecoveryPoint) -> dict:
    return {**point.__dict__, "completed_at": point.completed_at.isoformat(),
            "locked_until": point.locked_until.isoformat()}


def _point(item: dict) -> RecoveryPoint:
    return RecoveryPoint(**{**item, "completed_at": datetime.fromisoformat(item["completed_at"]),
                            "locked_until": datetime.fromisoformat(item["locked_until"])})
