from app.providers.base import CloudProvider, Vocabulary


class GcpProvider(CloudProvider):
    id = "gcp"
    name = "Google Cloud"
    document_file = "main.tf.json"

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

    def tag_policy(self):
        from app.providers.gcp.labels import LabelPolicy

        return LabelPolicy()

    def project(self):
        from app.providers.gcp.project.toolkit import gcp_project

        return gcp_project()

    def teardown(self):
        from app.providers.gcp.teardown import gcp_teardown

        return gcp_teardown()

    def resources(self):
        from app.providers.gcp.releases import TerraformResourceClassifier

        return TerraformResourceClassifier()

    def landing_zone(self):
        from app.providers.gcp.landing_zone.toolkit import gcp_landing_zone

        return gcp_landing_zone()
