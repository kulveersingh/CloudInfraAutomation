from app.providers.base import CloudProvider, Vocabulary
from app.synth.toolkit import ProjectToolkit


class AwsProvider(CloudProvider):
    id = "aws"
    name = "Amazon Web Services"

    def vocabulary(self):
        return Vocabulary(isolation_unit="account", hierarchy_node="OU", iac_document="CloudFormation template",
                          deploy_unit="stack", preventive_policy="SCP", private_network="VPC",
                          landing_zone_service="Control Tower", control_catalog="Control Tower controls")

    def default_regions(self):
        return ("us-east-1", "us-east-2")

    def project(self) -> ProjectToolkit:
        from app.providers.aws.project.toolkit import aws_project

        return aws_project()
