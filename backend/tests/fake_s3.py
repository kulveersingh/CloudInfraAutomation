"""An in-memory S3 with Object Lock, as MinIO enforces it (§23): versions keep a retain-until date, governance lets
only an identity allowed to bypass delete before it, compliance lets nobody. Identities share one store."""

import io
import itertools
from datetime import UTC, datetime, timedelta

from botocore.exceptions import ClientError

ALL = "*"
WORM = "Object is WORM protected and cannot be overwritten"


def error(code: str, message: str) -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": message}}, "fake")


class FakeStore:
    def __init__(self, clock=None):
        self.buckets: dict[str, dict] = {}
        self.clock = clock or (lambda: datetime.now(UTC))
        self._versions = itertools.count(1)

    def version_id(self) -> str:
        return f"v{next(self._versions)}"


class FakeS3:
    """One identity's client. `deletable` names the buckets it may delete in (ALL for every bucket)."""

    def __init__(self, store: FakeStore, deletable=frozenset(), bypass: bool = False):
        self._store = store
        self._deletable = deletable
        self._bypass = bypass

    # ---- buckets ----

    def create_bucket(self, Bucket, ObjectLockEnabledForBucket=False):
        if Bucket in self._store.buckets:
            raise error("BucketAlreadyOwnedByYou", "Your previous request to create the named bucket succeeded.")
        self._store.buckets[Bucket] = {"lock": {"ObjectLockEnabled": "Enabled"} if ObjectLockEnabledForBucket else None,
                                       "objects": {}}

    def put_object_lock_configuration(self, Bucket, ObjectLockConfiguration):
        self._bucket(Bucket)["lock"] = ObjectLockConfiguration

    def get_object_lock_configuration(self, Bucket):
        lock = self._bucket(Bucket)["lock"]
        if lock is None:
            raise error("ObjectLockConfigurationNotFoundError", "Object Lock configuration does not exist")
        return {"ObjectLockConfiguration": lock}

    # ---- objects ----

    def put_object(self, Bucket, Key, Body, Metadata=None, ContentType=None, ObjectLockMode=None,
                   ObjectLockRetainUntilDate=None):
        bucket = self._bucket(Bucket)
        default = ((bucket["lock"] or {}).get("Rule") or {}).get("DefaultRetention")
        if ObjectLockMode is None and default:
            ObjectLockMode = default["Mode"]
            ObjectLockRetainUntilDate = self._store.clock() + timedelta(days=default["Days"])
        bucket["objects"].setdefault(Key, []).append({
            "VersionId": self._store.version_id(), "Body": Body if isinstance(Body, bytes) else Body.encode(),
            "Metadata": dict(Metadata or {}), "ObjectLockMode": ObjectLockMode,
            "ObjectLockRetainUntilDate": ObjectLockRetainUntilDate})
        return {}

    def get_object(self, Bucket, Key):
        versions = self._bucket(Bucket)["objects"].get(Key)
        if not versions:
            raise error("NoSuchKey", "The specified key does not exist.")
        latest = versions[-1]
        found = {"Body": io.BytesIO(latest["Body"]), "Metadata": latest["Metadata"]}
        if latest["ObjectLockMode"]:
            found.update(ObjectLockMode=latest["ObjectLockMode"],
                         ObjectLockRetainUntilDate=latest["ObjectLockRetainUntilDate"])
        return found

    def list_objects_v2(self, Bucket, Prefix=""):
        keys = sorted(key for key, versions in self._bucket(Bucket)["objects"].items() if versions and key.startswith(Prefix))
        return {"Contents": [{"Key": key} for key in keys]} if keys else {}

    def list_object_versions(self, Bucket, Prefix=""):
        return {"Versions": [{"Key": key, "VersionId": version["VersionId"]}
                             for key, versions in self._bucket(Bucket)["objects"].items() if key.startswith(Prefix)
                             for version in versions]}

    def delete_object(self, Bucket, Key, VersionId=None, BypassGovernanceRetention=False):
        bucket = self._bucket(Bucket)
        if self._deletable != ALL and Bucket not in self._deletable:
            raise error("AccessDenied", "Access Denied.")
        versions = bucket["objects"].get(Key, [])
        version = next((item for item in versions if VersionId in (None, item["VersionId"])), None)
        if version is None:
            return {}
        locked = version["ObjectLockMode"] and version["ObjectLockRetainUntilDate"] > self._store.clock()
        bypassed = version["ObjectLockMode"] == "GOVERNANCE" and BypassGovernanceRetention and self._bypass
        if locked and not bypassed:
            raise error("AccessDenied", WORM)
        versions.remove(version)
        return {}

    def _bucket(self, name: str) -> dict:
        if name not in self._store.buckets:
            raise error("NoSuchBucket", "The specified bucket does not exist")
        return self._store.buckets[name]
