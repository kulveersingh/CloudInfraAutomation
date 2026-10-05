import json
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.adapters.ports import BackupPort, BackupSource, RecoveryPoint, VaultLock

STATE_FILE = "backup.json"
CENTRAL_VAULT = "cloudinfra-teardown-{region}"
RETENTION_DAYS = 60
SUPER_USER_ROLE = "CloudInfraBackupSuperUser"


class RecoveryPointLockedError(Exception):
    """Vault Lock in compliance mode: nobody can delete a recovery point before its minimum retention."""


class LocalBackup(BackupPort):
    """AWS Backup stand-in: backups complete at once, and the central vault's lock is enforced as in AWS (§21.9.1).

    `delete_recovery_point` exists only here, to test the lock the way a super user meets it in the console; the
    platform's port has no deletion."""

    def __init__(self, root, backup_account_id: str, clock: Callable[[], datetime] | None = None):
        self._state_file = Path(root) / "aws" / STATE_FILE
        self._account = backup_account_id
        self._clock = clock or (lambda: datetime.now(UTC))

    def back_up(self, source: BackupSource) -> RecoveryPoint:
        state = self._read()
        if source.source_arn in state["failing"]:
            raise RuntimeError(f"Backup of {source.source_arn} failed.")
        completed = self._clock()
        point = RecoveryPoint(
            arn=f"arn:aws:backup:{source.region}:{self._account}:recovery-point:{uuid.uuid4()}",
            vault=CENTRAL_VAULT.format(region=source.region), account_id=self._account, region=source.region,
            source_arn=source.source_arn, resource_type=source.resource_type, completed_at=completed,
            locked_until=completed + timedelta(days=RETENTION_DAYS))
        state["recovery_points"].append(_point_json(point))
        self._write(state)
        return point

    def vault_lock(self, region: str) -> VaultLock:
        lock = self._read()["locks"].get(region, {"locked": True, "min_retention_days": RETENTION_DAYS})
        return VaultLock(locked=lock["locked"], min_retention_days=lock["min_retention_days"])

    def recovery_point(self, arn: str) -> RecoveryPoint | None:
        return next((point for point in self.recovery_points() if point.arn == arn), None)

    def restore(self, recovery_point_arn: str, account_id: str, region: str, physical_name: str) -> None:
        point = self.recovery_point(recovery_point_arn)
        if point is None:
            raise KeyError(f"Recovery point {recovery_point_arn} does not exist.")
        state = self._read()
        state["restores"].append({"recovery_point": point.arn, "account": account_id, "region": region,
                                  "physical_name": physical_name, "resource_type": point.resource_type})
        self._write(state)

    # ---- local helpers: inspection, failure injection and the super user's console ----

    def recovery_points(self) -> list[RecoveryPoint]:
        return [_point(item) for item in self._read()["recovery_points"]]

    def restores(self) -> list[dict]:
        return self._read()["restores"]

    def fail_backups_of(self, source_arn: str) -> None:
        state = self._read()
        state["failing"].append(source_arn)
        self._write(state)

    def clear_failures(self) -> None:
        state = self._read()
        state["failing"] = []
        self._write(state)

    def set_vault_lock(self, region: str, locked: bool, min_retention_days: int) -> None:
        state = self._read()
        state["locks"][region] = {"locked": locked, "min_retention_days": min_retention_days}
        self._write(state)

    def delete_recovery_point(self, arn: str, role: str, at: datetime) -> None:
        point = self.recovery_point(arn)
        if at < point.locked_until:
            raise RecoveryPointLockedError(f"{arn} is locked until {point.locked_until.isoformat()}.")
        if role != SUPER_USER_ROLE:
            raise PermissionError(f"Only {SUPER_USER_ROLE} can delete recovery points.")
        state = self._read()
        state["recovery_points"] = [item for item in state["recovery_points"] if item["arn"] != arn]
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
