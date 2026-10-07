from app.providers.base import CloudProvider, Vocabulary

# Azure's fixed region pairs (geo-redundant storage replicates to the pair); regions without a pair are absent.
REGION_PAIRS = {
    "eastus": "westus", "eastus2": "centralus", "centralus": "eastus2", "westus": "eastus", "westus2": "westcentralus",
    "westcentralus": "westus2", "westus3": "eastus", "northcentralus": "southcentralus",
    "southcentralus": "northcentralus", "canadacentral": "canadaeast", "canadaeast": "canadacentral",
    "northeurope": "westeurope", "westeurope": "northeurope", "uksouth": "ukwest", "ukwest": "uksouth",
    "francecentral": "francesouth", "germanywestcentral": "germanynorth", "swedencentral": "swedensouth",
    "switzerlandnorth": "switzerlandwest", "norwayeast": "norwaywest", "australiaeast": "australiasoutheast",
    "australiasoutheast": "australiaeast", "japaneast": "japanwest", "japanwest": "japaneast",
    "koreacentral": "koreasouth", "southeastasia": "eastasia", "eastasia": "southeastasia",
    "centralindia": "southindia", "brazilsouth": "southcentralus",
}


class AzureProvider(CloudProvider):
    id = "azure"
    name = "Azure"
    document_file = "main.json"

    def vocabulary(self):
        return Vocabulary(cloud="Azure", isolation_unit="subscription", hierarchy_node="management group",
                          iac_document="ARM template", deploy_unit="deployment stack",
                          preventive_policy="Azure Policy", private_network="VNet",
                          firewall_group="network security group", landing_zone_service="Azure Landing Zones",
                          control_catalog="Azure Policy initiatives")

    def default_regions(self):
        return ("eastus2", "centralus")

    def region_pairs(self):
        """The region geo-redundant storage replicates to, for each region that has a pair (MC4-4)."""
        return dict(REGION_PAIRS)

    def region_pair(self, region: str) -> str | None:
        return REGION_PAIRS.get(region)

    def network_problems(self, network) -> list[str]:
        from app.providers.azure.networks import azure_network_problems

        return azure_network_problems(network)

    def project(self):
        from app.providers.azure.project.toolkit import azure_project

        return azure_project(REGION_PAIRS.get)

    def teardown(self):
        from app.providers.azure.teardown import azure_teardown

        return azure_teardown()

    def resources(self):
        from app.providers.azure.releases import AzureResourceClassifier

        return AzureResourceClassifier()

    def landing_zone(self):
        from app.providers.azure.landing_zone.toolkit import azure_landing_zone

        return azure_landing_zone()
