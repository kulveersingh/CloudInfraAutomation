from app.providers.gcp.project.capabilities import (
    DUAL_REGION_LOCATIONS,
    EventSource,
    GcpBlock,
    GrantTarget,
    continent,
)

ROLES = {"read": "roles/storage.objectViewer", "write": "roles/storage.objectCreator",
         "readwrite": "roles/storage.objectUser"}
NONCURRENT_VERSION_DAYS = 30
ABORT_UPLOAD_DAYS = 7
OBJECT_FINALIZED = "google.cloud.storage.object.v1.finalized"


class CloudStorageBucketBlock(GcpBlock, GrantTarget, EventSource):
    type_name = "storage.bucket"
    display_name = "Cloud Storage bucket"
    category = "Storage"
    multi_region = "replicated"
    provider_types = ("google_storage_bucket",)
    removal = "deleted only if empty"  # force_destroy = false: the deploy fails rather than delete objects

    def emit(self, document):
        body = {"name": self.naming.bucket_name(), "location": self._location(),
                "uniform_bucket_level_access": True, "public_access_prevention": "enforced",
                "versioning": {"enabled": True}, "force_destroy": False,
                "lifecycle_rule": [
                    {"condition": {"days_since_noncurrent_time": NONCURRENT_VERSION_DAYS}, "action": {"type": "Delete"}},
                    {"condition": {"age": ABORT_UPLOAD_DAYS}, "action": {"type": "AbortIncompleteMultipartUpload"}}]}
        if self.spans_regions:
            regions = self.request.resilience.selected_regions()
            body["custom_placement_config"] = {"data_locations": [region.upper() for region in regions]}
            body.update({"rpo": "ASYNC_TURBO"} if self.request.resilience.mode == "ha" else {})
        document.add_resource("google_storage_bucket", self.spec.id, self.primary_only(body))
        document.add_output(f"{self.spec.id}_name", {"value": self.naming.bucket_name()})

    def grants(self, access, prefix, member, source_id):
        body = {"bucket": self.naming.bucket_name(), "role": ROLES[access], "member": member}
        body.update({"condition": self._prefix_condition(prefix)} if prefix else {})
        return [("google_storage_bucket_iam_member", f"{source_id}-{self.spec.id}-{access}", self.primary_only(body))]

    def environment(self):
        return {self.naming.environment_variable("BUCKET"): self.naming.bucket_name()}

    def event_trigger(self):
        return {"event_type": OBJECT_FINALIZED, "event_filters": {"attribute": "bucket", "value": self.naming.bucket_name()},
                "trigger_region": self._trigger_region()}

    def read_grant(self, member, source_id):
        body = {"bucket": self.naming.bucket_name(), "role": ROLES["read"], "member": member}
        return "google_storage_bucket_iam_member", f"{source_id}-{self.spec.id}-events", self.primary_only(body)

    def contract_entry(self):
        return {"bucketName": self.naming.bucket_name()}

    def _location(self) -> str:
        primary = self.request.resilience.primary_region
        return DUAL_REGION_LOCATIONS[continent(primary)] if self.spans_regions else "${var.region}"

    def _trigger_region(self) -> str:
        return self._location().lower() if self.spans_regions else "${var.region}"

    def _prefix_condition(self, prefix: str) -> dict:
        objects = f"projects/_/buckets/{self.naming.bucket_name()}/objects/{prefix}"
        return {"title": f"{self.spec.id} {prefix}", "expression": f'resource.name.startsWith("{objects}")'}


