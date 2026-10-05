from app.providers.gcp.project.capabilities import FIRESTORE_MULTI_REGIONS, GcpBlock, GrantTarget, continent

ROLES = {"read": "roles/datastore.viewer", "write": "roles/datastore.user", "readwrite": "roles/datastore.user"}
PROTECTED = ('${contains(["stage", "prod"], var.environment_name) ? "DELETE_PROTECTION_ENABLED" : '
             '"DELETE_PROTECTION_DISABLED"}')


class FirestoreDatabaseBlock(GcpBlock, GrantTarget):
    """Firestore in Native mode: schemaless, so there are no key settings (unlike DynamoDB)."""

    type_name = "database.table"
    display_name = "Firestore database"
    category = "Databases"
    multi_region = "global"
    provider_types = ("google_firestore_database",)
    retained_on_removal = True  # deletion_policy ABANDON keeps the data when the service is removed

    def emit(self, document):
        document.add_resource("google_firestore_database", self.spec.id, self.primary_only({
            "project": "${var.project_id}", "name": self.naming.database_id(), "location_id": self._location(),
            "type": "FIRESTORE_NATIVE", "point_in_time_recovery_enablement": "POINT_IN_TIME_RECOVERY_ENABLED",
            "delete_protection_state": PROTECTED, "deletion_policy": "ABANDON"}))
        document.add_output(f"{self.spec.id}_name", {"value": self.naming.database_id()})

    def grants(self, access, prefix, member, source_id):
        database = f"projects/${{var.project_id}}/databases/{self.naming.database_id()}"
        return [("google_project_iam_member", f"{source_id}-{self.spec.id}-{access}", self.primary_only({
            "project": "${var.project_id}", "role": ROLES[access], "member": member,
            "condition": {"title": f"{self.spec.id} only", "expression": f'resource.name.startsWith("{database}")'}}))]

    def environment(self):
        return {self.naming.environment_variable("DATABASE"): self.naming.database_id()}

    def contract_entry(self):
        return {"databaseId": self.naming.database_id()}

    def _location(self) -> str:
        if not self.spans_regions:
            return "${var.region}"
        return FIRESTORE_MULTI_REGIONS[continent(self.request.resilience.primary_region)]
