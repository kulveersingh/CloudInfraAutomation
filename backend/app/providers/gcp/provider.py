from app.errors import ValidationFailedError
from app.providers.base import CloudProvider, Vocabulary


class GcpProvider(CloudProvider):
    id = "gcp"
    name = "Google Cloud"

    def vocabulary(self):
        return Vocabulary(cloud="Google Cloud", isolation_unit="project", hierarchy_node="folder",
                          iac_document="Terraform configuration", deploy_unit="Infrastructure Manager deployment",
                          preventive_policy="organization policy", private_network="Shared VPC",
                          firewall_group="network tag", landing_zone_service="Google Cloud Setup",
                          control_catalog="Security Command Center postures")

    def default_regions(self):
        return ("us-east1", "us-east4")

    def network_problems(self, network) -> list[str]:
        from app.providers.gcp.networks import gcp_network_problems

        return gcp_network_problems(network)

    def project(self):
        raise ValidationFailedError("Projects on Google Cloud are not available yet.")

    def teardown(self):
        raise ValidationFailedError("Teardowns on Google Cloud are not available yet.")

    def resources(self):
        raise ValidationFailedError("Releases on Google Cloud are not available yet.")

    def landing_zone(self):
        raise ValidationFailedError("The Google Cloud landing zone is not available yet.")
