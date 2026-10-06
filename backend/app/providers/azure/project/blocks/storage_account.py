from app.providers.azure.project.capabilities import (
    KEPT,
    LOCATION,
    AzureBlock,
    EventSource,
    GrantTarget,
    identity_id,
    principal_of,
    resource_id,
    role_assignment,
)
from app.providers.azure.project.naming import bare, variable
from app.providers.azure.project.template import STRING, ArmTemplate

API = "2023-05-01"
STORAGE = "Microsoft.Storage/storageAccounts"
CONTAINER = "data"
READER = "2a2b9908-6ea1-4ae2-8e65-a410df84e7d1"  # Storage Blob Data Reader
CONTRIBUTOR = "ba92f5b4-2d11-453d-a403-e96b0029c9fe"  # Storage Blob Data Contributor
SKUS = {"single": "Standard_ZRS", "dr": "Standard_GZRS", "ha": "Standard_RAGZRS"}
BLOBS = "Microsoft.Storage/storageAccounts/blobServices/containers/blobs"
PREFIX_ACTIONS = {"read": ("read",), "write": ("write", "add/action"), "readwrite": ("read", "write", "add/action")}
NONCURRENT_VERSION_DAYS = 30
SOFT_DELETE_DAYS = 7


def blob_path_condition(access: str, prefix: str) -> str:
    """ABAC: the role's blob actions apply only under the prefix (§22.11.3)."""
    actions = " AND ".join(f"!(ActionMatches{{'{BLOBS}/{action}'}})" for action in PREFIX_ACTIONS[access])
    return f"(({actions}) OR (@Resource[{BLOBS}:path] StringStartsWith '{prefix}'))"


class StorageAccountBlock(AzureBlock, GrantTarget, EventSource):
    """A storage account with one private container. Kept on removal: it lives in the data stack (MC4-2). Its
    private endpoint and Event Grid topic are in the shared stack."""

    type_name = "storage.bucket"
    display_name = "Storage account"
    category = "Storage"
    multi_region = "replicated"
    provider_types = (STORAGE,)
    retained_on_removal = True
    removal = KEPT

    @property
    def _name(self) -> str:
        return variable(self.naming.variable)

    @property
    def _id(self) -> str:
        return resource_id(STORAGE, f"variables('{self.naming.variable}')")

    def emit(self, documents):
        self.declare(documents, self.naming.variable, self.naming.storage_account())
        data, item = documents.data, self.spec.id
        data.add_resource({"type": STORAGE, "apiVersion": API, "comments": item, "name": self._name,
                           "location": LOCATION, "kind": "StorageV2",
                           "sku": {"name": SKUS[self.request.resilience.mode]}, "properties": {
                               "allowSharedKeyAccess": False, "allowBlobPublicAccess": False,
                               "minimumTlsVersion": "TLS1_2", "supportsHttpsTrafficOnly": True,
                               "publicNetworkAccess": "Disabled" if self.attached else "Enabled"}})
        account = f"[{self._id}]"
        data.add_resource({"type": f"{STORAGE}/blobServices", "apiVersion": API, "comments": item,
                           "name": f"[format('{{0}}/default', {bare(self._name)})]", "dependsOn": [account],
                           "properties": {"isVersioningEnabled": True,
                                          "deleteRetentionPolicy": {"enabled": True, "days": SOFT_DELETE_DAYS},
                                          "containerDeleteRetentionPolicy": {"enabled": True, "days": SOFT_DELETE_DAYS}}})
        data.add_resource({"type": f"{STORAGE}/blobServices/containers", "apiVersion": API, "comments": item,
                           "name": f"[format('{{0}}/default/{CONTAINER}', {bare(self._name)})]",
                           "dependsOn": [f"[resourceId('{STORAGE}/blobServices', {bare(self._name)}, 'default')]"],
                           "properties": {"publicAccess": "None"}})
        data.add_resource({"type": f"{STORAGE}/managementPolicies", "apiVersion": API, "comments": item,
                           "name": f"[format('{{0}}/default', {bare(self._name)})]", "dependsOn": [account],
                           "properties": {"policy": {"rules": [{
                               "enabled": True, "name": "expire-noncurrent-versions", "type": "Lifecycle",
                               "definition": {"filters": {"blobTypes": ["blockBlob"]}, "actions": {"version": {
                                   "delete": {"daysAfterCreationGreaterThan": NONCURRENT_VERSION_DAYS}}}}}]}}})
        if self.attached:
            add_private_endpoint(documents.shared, item, account, "blob")
        data.add_output(f"{self.naming.variable}", {"type": "string", "value": self._name})

    def grants(self, access, prefix, identity, comment):
        role = READER if access == "read" else CONTRIBUTOR
        condition = blob_path_condition(access, prefix) if prefix else None
        return [role_assignment(self._container_scope(), role, principal_of(identity), comment,
                                [f"[{identity_id(identity)}]"], condition)]

    def environment(self):
        return {self.naming.environment_variable("ACCOUNT"): self._name,
                self.naming.environment_variable("CONTAINER"): CONTAINER}

    def topic(self):
        return f"concat({bare(self._name)}, '-events')"

    def event_filter(self, prefix, suffix):
        found = {"includedEventTypes": ["Microsoft.Storage.BlobCreated"],
                 "subjectBeginsWith": f"/blobServices/default/containers/{CONTAINER}/blobs/{prefix}"}
        return {**found, **({"subjectEndsWith": suffix} if suffix else {})}

    def read_grant(self, identity, comment):
        return role_assignment(self._container_scope(), READER, principal_of(identity), comment,
                               [f"[{identity_id(identity)}]"])

    def add_topic(self, documents) -> None:
        documents.shared.add_resource({"type": "Microsoft.EventGrid/systemTopics", "apiVersion": "2022-06-15",
                                       "comments": self.spec.id, "name": f"[{self.topic()}]", "location": LOCATION,
                                       "properties": {"source": f"[{self._id}]",
                                                      "topicType": "Microsoft.Storage.StorageAccounts"}})

    def contract_entry(self):
        return {"account": self._name, "container": CONTAINER}

    def _container_scope(self) -> str:
        return (f"[format('Microsoft.Storage/storageAccounts/{{0}}/blobServices/default/containers/{CONTAINER}', "
                f"{bare(self._name)})]")


def add_private_endpoint(template: ArmTemplate, item: str, target: str, group: str, same_stack: bool = False) -> None:
    """A private endpoint in the registered endpoints subnet; DNS comes from the landing zone (A5). A target in an
    earlier stack is already deployed, and ARM refuses a dependency outside the template."""
    template.add_parameter("endpointSubnetId", STRING)
    template.add_resource({"type": "Microsoft.Network/privateEndpoints", "apiVersion": "2024-05-01", "comments": item,
                           "name": f"pe-{item}-{group.lower()}", "location": LOCATION,
                           "dependsOn": [target] if same_stack else [], "properties": {
                               "subnet": {"id": "[parameters('endpointSubnetId')]"},
                               "privateLinkServiceConnections": [{"name": f"{item}-{group.lower()}", "properties": {
                                   "privateLinkServiceId": target, "groupIds": [group]}}]}})
