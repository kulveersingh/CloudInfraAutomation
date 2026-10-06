from app.providers.azure.project.capabilities import LOCATION
from app.providers.azure.project.naming import VAULT_NAME, variable
from app.providers.azure.project.schema import AzureResourceTypes
from app.providers.azure.project.template import STRING, ArmDocuments
from app.synth.blocks.base import Block
from app.synth.synthesizer import IacDialect

KEY_VAULT_API = "2023-07-01"
SOFT_DELETE_DAYS = 90
COMMON = {"projectName": STRING, "environmentName": STRING, "location": STRING,
          "resilienceMode": {**STRING, "defaultValue": "single"}, "costCenter": STRING}
APP = {"regionRole": {**STRING, "defaultValue": "primary", "allowedValues": ["primary", "secondary"]},
       "activationState": {**STRING, "defaultValue": "active", "allowedValues": ["active", "standby"]}}


class ArmTemplateDialect(IacDialect):
    """Azure documents are two ARM templates applied as deployment stacks (MC4-1, MC4-2): `data` keeps what is
    removed from it, `app` is deployed per region and deletes it. Every resource that can carry tags gets the
    ownership tags; the contract goes to a Key Vault secret."""

    def __init__(self, types: AzureResourceTypes):
        self._types = types

    def start(self, request):
        documents = ArmDocuments()
        ownership = request.ownership
        tags = {"org:project": "[parameters('projectName')]", "org:environment": "[parameters('environmentName')]",
                "org:portfolio": ownership.portfolio_id, "org:product": ownership.product_id,
                "org:data-classification": ownership.data_classification,
                "org:resilience": "[parameters('resilienceMode')]", "org:cost-center": "[parameters('costCenter')]",
                "org:managed-by": "cloudinfra"}
        for template in documents.both():
            for name, body in COMMON.items():
                template.add_parameter(name, body)
            template.set_variable("tags", tags)
        for name, body in APP.items():
            documents.app.add_parameter(name, body)
        if request.resilience.is_multi_region:
            documents.data.add_parameter("secondaryLocation", STRING)
        return documents

    def add_block(self, document, block: Block):
        block.emit(document)

    def finish(self, document, request, blocks: dict[str, Block]):
        if any(block.uses_network for block in blocks.values()):
            document.app.add_parameter("subnetId", STRING)
            document.data.add_parameter("endpointSubnetId", STRING)
        self._contract(document, blocks)
        for template in document.both():
            for resource in template.resources():
                if self._taggable(resource):
                    resource["tags"] = variable("tags")
        return document.to_dict()

    def _taggable(self, resource: dict) -> bool:
        schema = self._types.schema(resource["type"], resource["apiVersion"])
        if schema is None:  # Tier-2 types: top-level resources carry tags
            return resource["type"].count("/") == 1
        return "tags" in schema["properties"]

    def _contract(self, document: ArmDocuments, blocks: dict[str, Block]) -> None:
        """The infrastructure contract, in a Key Vault secret, so application repos can discover resources."""
        data = document.data
        data.set_variable("vaultName", VAULT_NAME)
        data.set_variable("contract", {
            "contractVersion": "1", "project": "[parameters('projectName')]",
            "environment": "[parameters('environmentName')]", "resilienceMode": "[parameters('resilienceMode')]",
            "resources": {resource_id: {"type": block.type_name, **block.contract_entry()}
                          for resource_id, block in blocks.items()}})
        data.add_resource({"type": "Microsoft.KeyVault/vaults", "apiVersion": KEY_VAULT_API, "comments": "contract",
                           "name": variable("vaultName"), "location": LOCATION, "properties": {
                               "tenantId": "[subscription().tenantId]", "sku": {"family": "A", "name": "standard"},
                               "enableRbacAuthorization": True, "enablePurgeProtection": True,
                               "softDeleteRetentionInDays": SOFT_DELETE_DAYS}})
        data.add_resource({"type": "Microsoft.KeyVault/vaults/secrets", "apiVersion": KEY_VAULT_API,
                           "comments": "contract", "name": "[format('{0}/contract', variables('vaultName'))]",
                           "dependsOn": ["[resourceId('Microsoft.KeyVault/vaults', variables('vaultName'))]"],
                           "properties": {"value": "[string(variables('contract'))]"}})
