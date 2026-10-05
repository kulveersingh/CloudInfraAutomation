from app.releases.plan import ChangeSpec
from app.releases.risk import ResourceClassifier

STATEFUL_TYPES = frozenset({
    "google_storage_bucket", "google_firestore_database", "google_sql_database_instance", "google_sql_database",
    "google_alloydb_cluster", "google_alloydb_instance", "google_spanner_instance", "google_spanner_database",
    "google_bigtable_instance", "google_bigtable_table", "google_bigquery_dataset", "google_bigquery_table",
    "google_filestore_instance", "google_pubsub_subscription", "google_kms_crypto_key", "google_kms_key_ring",
    "google_secret_manager_secret",
})
PERMISSION_TYPES = frozenset({"google_service_account", "google_service_account_key", "google_iam_deny_policy",
                              "google_org_policy_policy", "google_organization_policy", "google_project_organization_policy"})
ACTIONS = {("create",): "Add", ("update",): "Modify", ("delete",): "Remove"}
REPLACEMENTS = {("delete", "create"), ("create", "delete")}


class TerraformResourceClassifier(ResourceClassifier):
    """Which Terraform resource types hold data, and which change permissions."""

    def is_stateful(self, resource_type):
        return resource_type in STATEFUL_TYPES

    def is_permission(self, resource_type):
        return resource_type in PERMISSION_TYPES or "_iam_" in resource_type

    def rows(self, document):
        return [(f"{type_name}.{name}", type_name) for type_name, resources in document.get("resource", {}).items()
                for name in resources]


class TerraformPlanReader:
    """Release rows from `terraform show -json` of a saved plan (an Infrastructure Manager preview's plan): managed
    resources that change, with delete-and-create shown as a replacement."""

    def changes(self, plan: dict) -> list[ChangeSpec]:
        return [row for change in plan.get("resource_changes", []) if change["mode"] == "managed"
                for row in self._row(change)]

    def _row(self, change: dict) -> list[ChangeSpec]:
        actions = tuple(change["change"]["actions"])
        if actions in REPLACEMENTS:
            return [ChangeSpec(action="Modify", logical_id=change["address"], resource_type=change["type"],
                               replacement=True)]
        action = ACTIONS.get(actions)
        return [ChangeSpec(action=action, logical_id=change["address"], resource_type=change["type"])] if action else []
