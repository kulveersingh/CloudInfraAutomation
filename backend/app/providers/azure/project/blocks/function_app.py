from app.providers.azure.project.blocks.storage_account import API as STORAGE_API
from app.providers.azure.project.capabilities import (
    IDENTITY_API,
    LOCATION,
    AzureBlock,
    Workload,
    identity_id,
    principal_of,
    role_assignment,
)
from app.providers.azure.project.naming import CODE_NAME, bare, camel, variable
from app.providers.azure.project.template import STRING
from app.synth.blocks.settings import ChoiceSetting, IntegerSetting, TextSetting

WEB_API = "2024-04-01"
RUNTIME_VERSIONS = {"python": "3.12", "node": "22", "dotnet-isolated": "8.0", "java": "21", "powershell": "7.4"}
CODE = "codeName"
BLOB_OWNER = "b7e6dc6d-f1e8-4753-8033-0f276bb0955b"  # Storage Blob Data Owner, for the host's own storage
ACTIVE = "[equals(parameters('activationState'), 'active')]"


class FlexFunctionBlock(AzureBlock, Workload):
    """A Flex Consumption function app with its own user-assigned identity. The identity, its roles and the code
    container are in the shared stack, and the code account (one per project) in the data stack; the plan and app
    are in the app stack of every region (§22.11.3)."""

    type_name = "compute.function"
    display_name = "Function app (Flex Consumption)"
    category = "Compute"
    multi_region = "replicated"
    provider_types = ("Microsoft.Web/sites",)
    settings = (
        ChoiceSetting("runtime", "Runtime", "python", tuple(RUNTIME_VERSIONS)),
        IntegerSetting("memory_mb", "Instance memory", 2048, 512, 4096, "MB"),
        IntegerSetting("max_instances", "Maximum instances", 100, 40, 1000, "instances"),
        TextSetting("function_name", "Function triggered by events", "main", r"^[A-Za-z][A-Za-z0-9_-]{0,127}$",
                    "1 to 128 letters, digits, _ and -, starting with a letter"),
    )

    def __init__(self, spec, request):
        super().__init__(spec, request)
        self._environment: dict[str, str] = {}
        self._subscriptions: list[tuple[object, str, str]] = []

    @property
    def uses_network(self):
        return self.attached

    @property
    def _app(self) -> str:
        return f"{camel(self.spec.id)}App"

    def identity(self):
        return self.naming.identity()

    def add_environment(self, variables):
        self._environment.update(variables)

    def add_subscription(self, source, prefix, suffix):
        self._subscriptions.append((source, prefix, suffix))

    def contract_entry(self):
        return {"functionApp": variable(self._app)}

    def emit(self, documents):
        self.declare(documents, self._app, self.naming.function_app())
        for template in documents.all():
            template.set_variable(CODE, CODE_NAME)
        self._code_account(documents.data)
        self._shared(documents.shared)
        self._app_stack(documents.app)

    @staticmethod
    def _code_account(data) -> None:
        if not data.has_resource("code"):  # one code account per project and environment
            data.add_resource({"type": "Microsoft.Storage/storageAccounts", "apiVersion": STORAGE_API,
                               "comments": "code", "name": variable(CODE), "location": LOCATION, "kind": "StorageV2",
                               "sku": {"name": "Standard_ZRS"}, "properties": {
                                   "allowSharedKeyAccess": False, "allowBlobPublicAccess": False,
                                   "minimumTlsVersion": "TLS1_2", "supportsHttpsTrafficOnly": True}})

    def _shared(self, shared) -> None:
        item, container = self.spec.id, f"app-{self.spec.id}"
        identity = f"[{identity_id(self.identity())}]"
        shared.add_resource({"type": "Microsoft.ManagedIdentity/userAssignedIdentities", "apiVersion": IDENTITY_API,
                             "comments": item, "name": self.identity(), "location": LOCATION})
        shared.add_resource({"type": "Microsoft.Storage/storageAccounts/blobServices/containers",
                             "apiVersion": STORAGE_API, "comments": item,
                             "name": f"[format('{{0}}/default/{container}', variables('codeName'))]",
                             "properties": {"publicAccess": "None"}})
        code_account = "[format('Microsoft.Storage/storageAccounts/{0}', variables('codeName'))]"
        shared.add_resource(role_assignment(code_account, BLOB_OWNER, principal_of(self.identity()), f"{item} host",
                                            [identity]))

    def _app_stack(self, app) -> None:
        item, plan = self.spec.id, f"[format('plan-{{0}}-{{1}}', '{self.spec.id}', parameters('location'))]"
        app.add_resource({"type": "Microsoft.Web/serverfarms", "apiVersion": WEB_API, "comments": item, "name": plan,
                          "location": LOCATION, "kind": "functionapp", "sku": {"name": "FC1", "tier": "FlexConsumption"},
                          "properties": {"reserved": True}})
        identity = f"[{identity_id(self.identity())}]"
        properties = {
            "serverFarmId": f"[resourceId('Microsoft.Web/serverfarms', {bare(plan)})]", "httpsOnly": True,
            "siteConfig": {"minTlsVersion": "1.2", "appSettings": self._settings()},
            "functionAppConfig": {
                "deployment": {"storage": {
                    "type": "blobContainer",
                    "value": f"[format('https://{{0}}.blob.{{1}}/app-{self.spec.id}', variables('codeName'), "
                             "environment().suffixes.storage)]",
                    "authentication": {"type": "UserAssignedIdentity", "userAssignedIdentityResourceId": identity}}},
                "scaleAndConcurrency": {"maximumInstanceCount": self.setting("max_instances"),
                                        "instanceMemoryMB": self.setting("memory_mb")},
                "runtime": {"name": self.setting("runtime"), "version": RUNTIME_VERSIONS[self.setting("runtime")]}}}
        if self.uses_network:
            app.add_parameter("subnetId", STRING)
            properties.update({"virtualNetworkSubnetId": "[parameters('subnetId')]", "publicNetworkAccess": "Disabled"})
        app.add_resource({"type": "Microsoft.Web/sites", "apiVersion": WEB_API, "comments": item,
                          "name": variable(self._app), "location": LOCATION, "kind": "functionapp,linux",
                          "identity": {"type": "UserAssigned", "userAssignedIdentities": {identity: {}}},
                          "dependsOn": [f"[resourceId('Microsoft.Web/serverfarms', {bare(plan)})]"],
                          "properties": properties})
        for source, prefix, suffix in self._subscriptions:
            self._subscription(app, source, prefix, suffix)

    def _settings(self) -> list[dict]:
        host = {"AzureWebJobsStorage__accountName": variable(CODE), "AzureWebJobsStorage__credential": "managedidentity",
                "AzureWebJobsStorage__clientId": f"[reference({identity_id(self.identity())}, '{IDENTITY_API}').clientId]"}
        return [{"name": name, "value": value} for name, value in {**host, **dict(sorted(self._environment.items()))}.items()]

    def _subscription(self, app, source, prefix: str, suffix: str) -> None:
        """Delivered only where the region is active: a DR standby region gets no events (§22.11.2)."""
        function = f"[format('{{0}}/functions/{{1}}', resourceId('Microsoft.Web/sites', variables('{self._app}')), " \
                   f"'{self.setting('function_name')}')]"
        app.add_resource({"type": "Microsoft.EventGrid/systemTopics/eventSubscriptions", "apiVersion": "2022-06-15",
                          "comments": f"{source.spec.id} → {self.spec.id}", "condition": ACTIVE,
                          "name": f"[format('{{0}}/{{1}}-{{2}}', {source.topic()}, '{self.spec.id}', parameters('location'))]",
                          "dependsOn": [f"[resourceId('Microsoft.Web/sites', variables('{self._app}'))]"],
                          "properties": {"destination": {"endpointType": "AzureFunction",
                                                         "properties": {"resourceId": function}},
                                         "filter": source.event_filter(prefix, suffix),
                                         "eventDeliverySchema": "EventGridSchema"}})
