from app.providers.azure.landing_zone.stacks.base import (
    LOCATION,
    ROLES_API,
    Stack,
    in_resource_group,
    role_definition,
)
from app.providers.azure.landing_zone.stacks.storage import locked_account

DATA_PROTECTION_API = "2024-04-01"
TEARDOWN_RETENTION_DAYS = 60
SOFT_DELETE_DAYS = 14
BACKUP_CONTRIBUTOR = "5e467623-bb1f-42f4-a55d-6e525e11384b"
VAULT_GROUP = "rg-cloudinfra-backup"
EXPORT_ACCOUNT = "[concat('stteardown', uniqueString(subscription().id))]"  # the account MC-4d exports Cosmos DB into


class VaultStack(Stack):
    """The backup subscription (MC5-10): per governed region a locked immutable Backup vault and a Resource Guard,
    and the locked export container for Cosmos DB; only the backup super users can manage them."""

    name = "lz-vault"
    description = "Locked Backup vaults, Resource Guards and the locked export container for teardowns"
    unmanaged = "detachAll"

    def resources(self, context):
        if not context.vends("backup"):  # teardowns then use the azure_backup_subscription setting
            return []
        resources = []
        for region in context.regions:
            vault = f"bv-teardown-{region}"
            resources += [{"type": "Microsoft.DataProtection/backupVaults", "apiVersion": DATA_PROTECTION_API,
                           "name": vault, "location": region, "identity": {"type": "SystemAssigned"}, "properties": {
                               "storageSettings": [{"datastoreType": "VaultStore", "type": "LocallyRedundant"}],
                               "securitySettings": {
                                   "immutabilitySettings": {"state": "Locked"},
                                   "softDeleteSettings": {"state": "AlwaysOn",
                                                          "retentionDurationInDays": SOFT_DELETE_DAYS}}}},
                          {"type": "Microsoft.DataProtection/resourceGuards", "apiVersion": DATA_PROTECTION_API,
                           "name": f"rgd-teardown-{region}", "location": region, "properties": {}},
                          {"type": "Microsoft.DataProtection/backupVaults/backupResourceGuardProxies",
                           "apiVersion": DATA_PROTECTION_API, "name": f"{vault}/DppResourceGuardProxy",
                           "dependsOn": [vault, f"rgd-teardown-{region}"], "properties": {
                               "resourceGuardResourceId": f"[resourceId('Microsoft.DataProtection/resourceGuards', "
                                                          f"'rgd-teardown-{region}')]"}}]
        resources += locked_account(EXPORT_ACCOUNT, context.home, TEARDOWN_RETENTION_DAYS, container="cloudinfra-teardown")
        resources.append({"type": "Microsoft.Authorization/roleAssignments", "apiVersion": ROLES_API,
                          "name": "[guid(resourceGroup().id, 'backup-super-users')]", "properties": {
                              "roleDefinitionId": role_definition(BACKUP_CONTRIBUTOR),
                              "principalId": context.answers.groups.backup_super_users, "principalType": "Group"}})
        return [in_resource_group("vault", context.subscription(context.unit("backup")), VAULT_GROUP, LOCATION,
                                  resources)]
