from app.providers.azure.project.blocks.storage_account import add_private_endpoint
from app.providers.azure.project.capabilities import (
    KEPT,
    LOCATION,
    SECONDARY,
    AzureBlock,
    GrantTarget,
    identity_id,
    principal_of,
    resource_id,
)
from app.providers.azure.project.naming import bare, variable
from app.synth.blocks.settings import TextSetting

API = "2024-11-15"
ACCOUNT = "Microsoft.DocumentDB/databaseAccounts"
DATABASE = CONTAINER = "data"
ROLES = {"read": "00000000-0000-0000-0000-000000000001", "write": "00000000-0000-0000-0000-000000000002",
         "readwrite": "00000000-0000-0000-0000-000000000002"}  # Cosmos DB built-in data reader / contributor
MAX_THROUGHPUT = 1000


class CosmosContainerBlock(AzureBlock, GrantTarget):
    """Cosmos DB for NoSQL: an account, a database and a container. Entra only, continuous backup; kept on removal
    (data stack). DR adds a read region, HA writes in every region (§22.11.3)."""

    type_name = "database.table"
    display_name = "Cosmos DB container"
    category = "Databases"
    multi_region = "global"
    provider_types = (ACCOUNT,)
    retained_on_removal = True
    removal = KEPT
    settings = (TextSetting("partition_key", "Partition key", "id", r"^[A-Za-z_][A-Za-z0-9_]{0,63}$",
                            "1 to 64 letters, digits and _, starting with a letter or _"),)

    @property
    def _name(self) -> str:
        return variable(self.naming.variable)

    @property
    def _id(self) -> str:
        return resource_id(ACCOUNT, f"variables('{self.naming.variable}')")

    def emit(self, documents):
        self.declare(documents, self.naming.variable, self.naming.cosmos_account())
        data, item = documents.data, self.spec.id
        locations = [{"locationName": LOCATION, "failoverPriority": 0, "isZoneRedundant": True}]
        if self.spans_regions:
            locations.append({"locationName": SECONDARY, "failoverPriority": 1, "isZoneRedundant": True})
        data.add_resource({"type": ACCOUNT, "apiVersion": API, "comments": item, "name": self._name, "location": LOCATION,
                           "kind": "GlobalDocumentDB", "properties": {
                               "databaseAccountOfferType": "Standard", "locations": locations,
                               "consistencyPolicy": {"defaultConsistencyLevel": "Session"}, "disableLocalAuth": True,
                               "enableMultipleWriteLocations": self.request.resilience.mode == "ha",
                               "backupPolicy": {"type": "Continuous",
                                                "continuousModeProperties": {"tier": "Continuous30Days"}},
                               "minimalTlsVersion": "Tls12",
                               "publicNetworkAccess": "Disabled" if self.attached else "Enabled"}})
        data.add_resource({"type": f"{ACCOUNT}/sqlDatabases", "apiVersion": API, "comments": item,
                           "name": f"[format('{{0}}/{DATABASE}', {bare(self._name)})]", "dependsOn": [f"[{self._id}]"],
                           "properties": {"resource": {"id": DATABASE}}})
        data.add_resource({"type": f"{ACCOUNT}/sqlDatabases/containers", "apiVersion": API, "comments": item,
                           "name": f"[format('{{0}}/{DATABASE}/{CONTAINER}', {bare(self._name)})]",
                           "dependsOn": [f"[resourceId('{ACCOUNT}/sqlDatabases', {bare(self._name)}, '{DATABASE}')]"],
                           "properties": {"resource": {"id": CONTAINER, "partitionKey": {
                               "paths": [f"/{self.setting('partition_key')}"], "kind": "Hash"}},
                               "options": {"autoscaleSettings": {"maxThroughput": MAX_THROUGHPUT}}}})
        if self.attached:
            add_private_endpoint(documents.shared, item, f"[{self._id}]", "Sql")

    def grants(self, access, prefix, identity, comment):
        definition = f"[resourceId('{ACCOUNT}/sqlRoleDefinitions', {bare(self._name)}, '{ROLES[access]}')]"
        return [{"type": f"{ACCOUNT}/sqlRoleAssignments", "apiVersion": API, "comments": comment,
                 "name": f"[format('{{0}}/{{1}}', {bare(self._name)}, guid(resourceGroup().id, '{comment}', '{access}'))]",
                 "dependsOn": [f"[{identity_id(identity)}]"],
                 "properties": {"roleDefinitionId": definition, "principalId": principal_of(identity),
                                "scope": f"[format('{{0}}/dbs/{DATABASE}/colls/{CONTAINER}', {self._id})]"}}]

    def environment(self):
        return {self.naming.environment_variable("ACCOUNT"): self._name,
                self.naming.environment_variable("DATABASE"): DATABASE,
                self.naming.environment_variable("CONTAINER"): CONTAINER}

    def contract_entry(self):
        return {"account": self._name, "database": DATABASE, "container": CONTAINER}
