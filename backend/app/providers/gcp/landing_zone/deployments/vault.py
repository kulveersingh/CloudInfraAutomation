from app.providers.gcp.landing_zone.deployments.base import (
    SECONDS_IN_A_DAY,
    TEARDOWN_RETENTION_DAYS,
    Deployment,
    group,
)

RETENTION_SECONDS = TEARDOWN_RETENTION_DAYS * SECONDS_IN_A_DAY
VAULT_ID = "cloudinfra-teardown"
DENIED = ["storage.googleapis.com/buckets.delete", "backupdr.googleapis.com/backupVaults.delete"]


def vault_bucket(region: str, project: str) -> str:
    return f"{VAULT_ID}-{region}-{project}"


class VaultDeployment(Deployment):
    """The teardown vault (MC3-6): per governed region a Bucket-Locked bucket and a Backup and DR vault, both
    keeping backups 60 days, and an IAM deny policy only the backup super users escape."""

    name = "lz-vault"
    description = "Teardown vault: locked buckets and Backup and DR vaults per region, deny policy"

    def build(self, context, document):
        project = context.unit("backup")
        for region in context.regions:
            document.add_resource("google_storage_bucket", region, {
                "project": project, "name": vault_bucket(region, project), "location": region,
                "uniform_bucket_level_access": True, "public_access_prevention": "enforced", "force_destroy": False,
                "retention_policy": {"retention_period": RETENTION_SECONDS, "is_locked": True}})
            document.add_resource("google_backup_dr_backup_vault", region, {
                "project": project, "location": region, "backup_vault_id": VAULT_ID,
                "backup_minimum_enforced_retention_duration": f"{RETENTION_SECONDS}s"})
        document.add_resource("google_iam_deny_policy", "vault", {
            "name": "protect-teardown-vault", "display_name": "Only backup super users may delete the vault",
            "parent": f'${{urlencode("cloudresourcemanager.googleapis.com/projects/{project}")}}',
            "rules": [{"deny_rule": {"denied_principals": ["principalSet://goog/public:all"],
                                     "exception_principals": [group(context.answers.groups.backup_super_users)],
                                     "denied_permissions": DENIED}}]})
        document.add_output("vault_project", {"value": project})
