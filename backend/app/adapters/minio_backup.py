"""A locked teardown vault in Docker for local testing (§23): MinIO with S3 Object Lock behind the backup port."""

import hashlib
import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.adapters.local_backup import RETENTION_DAYS, BackupStyle, RecoveryPointLockedError
from app.adapters.ports import BackupPort, BackupSource, RecoveryPoint, VaultLock
from app.config import Settings

CONTROL_BUCKET = "cloudinfra-vault"  # unlocked: the ref index, restores and injected failures
NOT_LOCKED = VaultLock(locked=False, min_retention_days=0)
NO_LOCK = frozenset({"NoSuchBucket", "ObjectLockConfigurationNotFoundError"})
WORM = "WORM"
DAYS_IN_A_YEAR = 365
JSON = "application/json"


def bucket_name(provider: str, region: str) -> str:
    """The locked bucket that stands in for one cloud's central vault in one region (V-3)."""
    return f"teardown-{provider}-{region}"


def _key(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _code(error: ClientError) -> str:
    return error.response["Error"]["Code"]


@dataclass(frozen=True)
class MinioVault:
    """The platform's connection to the store, and how long and in which mode it locks backups."""

    client: object
    mode: str
    retention: timedelta

    @classmethod
    def from_settings(cls, settings: Settings) -> "MinioVault":
        client = boto3.client("s3", endpoint_url=settings.vault_endpoint, region_name="us-east-1",
                              aws_access_key_id=settings.vault_access_key,
                              aws_secret_access_key=settings.vault_secret_key,
                              config=Config(s3={"addressing_style": "path"}))
        return cls(client, settings.vault_retention_mode, timedelta(days=settings.vault_retention_days))


class MinioBackup(BackupPort):
    """Each backup is an object in its region's locked bucket, retained until completion plus the retention. The
    lock is the store's: the platform's identity can neither delete nor bypass it (V-6), and `locked_until` is read
    back from the store. Refs and vault names keep each cloud's own shape (V-4)."""

    def __init__(self, client, backup_account_id: str, provider: str, style: BackupStyle,
                 clock: Callable[[], datetime] | None = None, retention: timedelta = timedelta(days=RETENTION_DAYS),
                 mode: str = "GOVERNANCE"):
        self._client = client
        self._account = backup_account_id
        self.provider = provider
        self._style = style
        self._clock = clock or (lambda: datetime.now(UTC))
        self.retention = retention
        self._mode = mode

    def back_up(self, source: BackupSource) -> RecoveryPoint:
        if self._exists(CONTROL_BUCKET, f"failures/{_key(source.source_ref)}"):
            raise RuntimeError(f"Backup of {source.source_ref} failed.")
        completed = self._clock()
        ref = self._style.ref(self._account, source.region, source.resource_type)
        point = RecoveryPoint(ref=ref, vault=self._style.vault(self._account, source.region, source.resource_type),
                              account_id=self._account, region=source.region, source_ref=source.source_ref,
                              resource_type=source.resource_type, completed_at=completed,
                              locked_until=completed + self.retention)
        bucket = bucket_name(self.provider, source.region)
        manifest = {**point.__dict__, "completed_at": completed.isoformat()}
        del manifest["locked_until"]
        try:
            self._client.put_object(Bucket=bucket, Key=_key(ref), Body=json.dumps(manifest), ContentType=JSON,
                                    Metadata={"ref": ref}, ObjectLockMode=self._mode,
                                    ObjectLockRetainUntilDate=point.locked_until)
        except ClientError as error:
            if _code(error) == "NoSuchBucket":
                raise RuntimeError(f"The vault bucket {bucket} does not exist: run the vault setup.") from error
            raise
        self._client.put_object(Bucket=CONTROL_BUCKET, Key=f"index/{_key(ref)}", Body=json.dumps({"bucket": bucket}),
                                ContentType=JSON)
        return point

    def vault_lock(self, region: str) -> VaultLock:
        """Locked when the bucket has Object Lock with a default retention of at least 60 days."""
        try:
            configuration = self._client.get_object_lock_configuration(Bucket=bucket_name(self.provider, region))
        except ClientError as error:
            if _code(error) in NO_LOCK:
                return NOT_LOCKED
            raise
        lock = configuration["ObjectLockConfiguration"]
        retention = lock.get("Rule", {}).get("DefaultRetention", {})
        days = retention.get("Days", retention.get("Years", 0) * DAYS_IN_A_YEAR)
        return VaultLock(locked=lock.get("ObjectLockEnabled") == "Enabled" and days >= RETENTION_DAYS,
                         min_retention_days=days)

    def recovery_point(self, ref: str) -> RecoveryPoint | None:
        bucket = self._bucket_of(ref)
        found = self._read(bucket, _key(ref)) if bucket else None
        if found is None:
            return None
        manifest = json.loads(found["Body"].read())
        return RecoveryPoint(**{**manifest, "completed_at": datetime.fromisoformat(manifest["completed_at"]),
                                "locked_until": found["ObjectLockRetainUntilDate"]})

    def restore(self, recovery_point_ref: str, account_id: str, region: str, physical_name: str) -> None:
        """Reads the backup back and records the restore; recreating the data store is the cloud's (V-Q2)."""
        point = self.recovery_point(recovery_point_ref)
        if point is None:
            raise KeyError(f"Recovery point {recovery_point_ref} does not exist.")
        record = {"recovery_point": point.ref, "account": account_id, "region": region, "physical_name": physical_name,
                  "resource_type": point.resource_type}
        self._client.put_object(Bucket=CONTROL_BUCKET, Key=f"restores/{self._clock().isoformat()}-{uuid.uuid4()}",
                                Body=json.dumps(record), ContentType=JSON)

    # ---- local helpers: inspection, failure injection and the super user's deletion ----

    def restores(self) -> list[dict]:
        return [json.loads(self._read(CONTROL_BUCKET, key)["Body"].read()) for key in self._keys("restores/")]

    def fail_backups_of(self, source_ref: str) -> None:
        self._client.put_object(Bucket=CONTROL_BUCKET, Key=f"failures/{_key(source_ref)}", Body=source_ref)

    def clear_failures(self) -> None:
        for key in self._keys("failures/"):
            self._client.delete_object(Bucket=CONTROL_BUCKET, Key=key)

    def delete_recovery_point(self, ref: str, client) -> None:
        """Deletes every version of the backup with `client`'s identity and the governance bypass; the store refuses
        unless that identity may bypass, the lock is governance, or the lock has ended."""
        bucket = self._bucket_of(ref)
        if bucket is None:
            raise KeyError(f"Recovery point {ref} does not exist.")
        for version in client.list_object_versions(Bucket=bucket, Prefix=_key(ref)).get("Versions", []):
            try:
                client.delete_object(Bucket=bucket, Key=version["Key"], VersionId=version["VersionId"],
                                     BypassGovernanceRetention=True)
            except ClientError as error:
                message = error.response["Error"]["Message"]
                raise (RecoveryPointLockedError if WORM in message else PermissionError)(message) from error

    def _bucket_of(self, ref: str) -> str | None:
        found = self._read(CONTROL_BUCKET, f"index/{_key(ref)}")
        return json.loads(found["Body"].read())["bucket"] if found else None

    def _keys(self, prefix: str) -> list[str]:
        return [item["Key"] for item in self._client.list_objects_v2(Bucket=CONTROL_BUCKET, Prefix=prefix)
                .get("Contents", [])]

    def _exists(self, bucket: str, key: str) -> bool:
        return self._read(bucket, key) is not None

    def _read(self, bucket: str, key: str) -> dict | None:
        try:
            return self._client.get_object(Bucket=bucket, Key=key)
        except ClientError as error:
            if _code(error) == "NoSuchKey":
                return None
            raise
