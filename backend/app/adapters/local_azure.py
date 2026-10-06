import uuid

from app.adapters.local_backup import BackupStyle
from app.adapters.local_cloud import LocalCloud
from app.adapters.ports import BootstrapOutputs, BootstrapRequest
from app.providers.azure.naming import resource_group_id

BACKUP_GROUP = "/subscriptions/{subscription}/resourceGroups/rg-cloudinfra-backup/providers"
# Cosmos DB backups die with the account, so its data is exported to a locked container instead (MC4-8).
EXPORTED_TYPES = frozenset({"Microsoft.DocumentDB/databaseAccounts"})
SUPER_USERS = "group:cloudinfra-backup-super-users"


class AzureBackupStyle(BackupStyle):
    """The backup subscription: a locked, immutable Backup vault per region for blobs, and a blob container with a
    locked 60-day immutability policy for Cosmos DB exports."""

    super_user = SUPER_USERS

    def vault(self, backup_account_id, region, resource_type):
        providers = BACKUP_GROUP.format(subscription=backup_account_id)
        if resource_type in EXPORTED_TYPES:
            account = f"stteardown{uuid.uuid5(uuid.NAMESPACE_URL, backup_account_id).hex[:12]}"
            return f"{providers}/Microsoft.Storage/storageAccounts/{account}/blobServices/default/containers/cloudinfra-teardown"
        return f"{providers}/Microsoft.DataProtection/backupVaults/bv-teardown-{region}"

    def ref(self, backup_account_id, region, resource_type):
        vault = self.vault(backup_account_id, region, resource_type)
        if resource_type in EXPORTED_TYPES:
            return f"{vault}/exports/{uuid.uuid4()}"
        return f"{vault}/backupInstances/{uuid.uuid4()}"


class LocalAzure(LocalCloud):
    """Azure stand-in: the project's resource group in the environment's subscription, and a user-assigned identity
    in it with a federated credential for the repository's environment (§22.11.2). Deployments run as the caller, so
    the deploy identity also applies the templates."""

    provider = "azure"

    def _outputs(self, request: BootstrapRequest) -> BootstrapOutputs:
        group = resource_group_id(request.account_id, request.project, request.environment)
        identity = (f"{group}/providers/Microsoft.ManagedIdentity/userAssignedIdentities/id-{request.project}-"
                    f"{request.environment}-deploy")
        return BootstrapOutputs(deployer_identity=identity, execution_identity=identity,
                                federation=str(uuid.uuid5(uuid.NAMESPACE_URL, identity)),
                                directory=str(uuid.uuid5(uuid.NAMESPACE_URL, "cloudinfra:azure:tenant")))

    def _backup_style(self):
        return AzureBackupStyle()
