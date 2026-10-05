from app.providers.base import CloudProvider, Vocabulary
from app.releases.risk import ResourceClassifier
from app.synth.toolkit import ProjectToolkit
from app.teardown.inventory import TeardownToolkit


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

    def teardown(self) -> TeardownToolkit:
        from app.providers.aws.teardown import aws_teardown

        return aws_teardown()

    def resources(self) -> ResourceClassifier:
        from app.providers.aws.releases import CloudFormationResourceClassifier

        return CloudFormationResourceClassifier()
