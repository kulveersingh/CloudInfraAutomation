import uuid

from app.adapters.local_backup import BackupStyle
from app.adapters.local_cloud import LocalCloud
from app.adapters.ports import BootstrapOutputs, BootstrapRequest

# Databases go to the Backup and DR vault; objects and Firestore exports to the Bucket-Locked bucket (§22.9.5).
BACKUP_AND_DR_TYPES = frozenset({"google_sql_database_instance", "google_alloydb_cluster"})
SUPER_USERS = "group:cloudinfra-backup-super-users"


class GcpBackupStyle(BackupStyle):
    """The vault project: a bucket per region with a locked 60-day retention policy (Bucket Lock), and a Backup and
    DR vault with an enforced 60-day minimum retention. After that only the super-user group may delete."""

    super_user = SUPER_USERS

    def vault(self, backup_account_id, region, resource_type):
        if resource_type in BACKUP_AND_DR_TYPES:
            return f"projects/{backup_account_id}/locations/{region}/backupVaults/cloudinfra-teardown"
        return f"cloudinfra-teardown-{region}-{backup_account_id}"

    def ref(self, backup_account_id, region, resource_type):
        vault = self.vault(backup_account_id, region, resource_type)
        if resource_type in BACKUP_AND_DR_TYPES:
            return f"{vault}/dataSources/{uuid.uuid4()}"
        return f"gs://{vault}/{uuid.uuid4()}/"


WORKLOAD_IDENTITY_PROVIDER = "projects/{project}/locations/global/workloadIdentityPools/cloudinfra-github/providers/github"


class LocalGcp(LocalCloud):
    """Google Cloud stand-in: Workload Identity Federation for GitHub, a deploy service account and the
    Infrastructure Manager service account in the environment's project (§22.9.1)."""

    provider = "gcp"

    def _outputs(self, request: BootstrapRequest) -> BootstrapOutputs:
        return BootstrapOutputs(deployer_identity=self._service_account(request, "deploy"),
                                execution_identity=self._service_account(request, "im"),
                                federation=WORKLOAD_IDENTITY_PROVIDER.format(project=request.account_id))

    def _service_account(self, request: BootstrapRequest, role: str) -> str:
        return f"cloudinfra-{request.project}-{role}@{request.account_id}.iam.gserviceaccount.com"

    def _backup_style(self):
        return GcpBackupStyle()
