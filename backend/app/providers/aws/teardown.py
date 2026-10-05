from app.adapters.ports import BOOTSTRAP_STACK
from app.providers.aws.project.toolkit import aws_project
from app.synth.blocks.registry import BlockRegistry
from app.synth.request import ProjectRequest
from app.synth.synthesizer import TemplateSynthesizer
from app.teardown.inventory import DataStore, DataStoreInventory, TeardownToolkit

NO_BACKUP_ACCOUNT = "No central Backup account is configured: add a Backup account to the landing zone first."
RETAINING_POLICIES = ("Retain", "RetainExceptOnCreate")
PRIMARY_ONLY = "IsPrimary"


class BackupTarget:
    """One kind of data store AWS Backup can protect. New database blocks add one (Open/Closed)."""

    types: tuple[str, ...] = ()
    name_property: str | None = None
    arn_pattern: str = ""

    def arn(self, name: str, account_id: str, region: str) -> str:
        return self.arn_pattern.format(name=name, account=account_id, region=region)


class S3BucketTarget(BackupTarget):
    types = ("AWS::S3::Bucket",)
    name_property = "BucketName"
    arn_pattern = "arn:aws:s3:::{name}"


class DynamoDbTableTarget(BackupTarget):
    types = ("AWS::DynamoDB::Table", "AWS::DynamoDB::GlobalTable")
    name_property = "TableName"
    arn_pattern = "arn:aws:dynamodb:{region}:{account}:table/{name}"


class RdsClusterTarget(BackupTarget):
    types = ("AWS::RDS::DBCluster",)
    name_property = "DBClusterIdentifier"
    arn_pattern = "arn:aws:rds:{region}:{account}:cluster:{name}"


class RdsInstanceTarget(BackupTarget):
    types = ("AWS::RDS::DBInstance",)
    name_property = "DBInstanceIdentifier"
    arn_pattern = "arn:aws:rds:{region}:{account}:db:{name}"


class EfsFileSystemTarget(BackupTarget):
    """AWS assigns file system ids, so the template never names one: teardown refuses until it can."""

    types = ("AWS::EFS::FileSystem",)
    arn_pattern = "arn:aws:elasticfilesystem:{region}:{account}:file-system/{name}"


class CloudFormationInventory(DataStoreInventory):
    """Finds the data stores an environment runs, from the CloudFormation template its current request generates."""

    def __init__(self, synthesizer: TemplateSynthesizer, blocks: BlockRegistry, targets: list[BackupTarget]):
        self._synthesizer = synthesizer
        self._blocks = blocks
        self._targets = {type_name: target for target in targets for type_name in target.types}

    @classmethod
    def default(cls) -> "CloudFormationInventory":
        toolkit = aws_project()
        return cls(toolkit.synthesizer, toolkit.blocks,
                   [S3BucketTarget(), DynamoDbTableTarget(), RdsClusterTarget(), RdsInstanceTarget(),
                    EfsFileSystemTarget()])

    def for_environment(self, request: ProjectRequest, environment: str, account_id: str,
                        regions: list[str]) -> tuple[list[DataStore], list[str]]:
        template = self._synthesizer.synthesize(request)
        stores: list[DataStore] = []
        problems: list[str] = []
        for service_id, logical_id, resource in self._main_resources(request, template):
            target = self._targets.get(resource["Type"])
            if target is None:
                continue
            for region in self._regions(resource, regions, request.resilience.primary_region):
                name = self._name(resource, target, request.project_name, account_id, region)
                if name is None:
                    problems.append(f"Cannot back up {service_id} ({resource['Type']}): its physical name is not in "
                                    "the template.")
                    break
                stores.append(DataStore(service_id, logical_id, resource["Type"], name, region, account_id,
                                        target.arn(name, account_id, region),
                                        resource.get("DeletionPolicy") in RETAINING_POLICIES))
        return stores, problems

    def not_backed_up(self, request: ProjectRequest) -> list[str]:
        template = self._synthesizer.synthesize(request)
        return [f"{service_id} ({request.resource(service_id).type}): rebuilt from the template and the application "
                "repository" for service_id, _, resource in self._main_resources(request, template)
                if resource["Type"] not in self._targets]

    def _main_resources(self, request: ProjectRequest, template: dict):
        for spec in request.resources:
            logical_id = self._blocks.create(spec, request).logical_id
            yield spec.id, logical_id, template["Resources"][logical_id]

    def _regions(self, resource: dict, regions: list[str], primary: str) -> list[str]:
        return [primary] if resource.get("Condition") == PRIMARY_ONLY else regions

    def _name(self, resource: dict, target: BackupTarget, project: str, account_id: str, region: str) -> str | None:
        value = resource.get("Properties", {}).get(target.name_property) if target.name_property else None
        text = value.get("Fn::Sub") if isinstance(value, dict) else value
        if not isinstance(text, str):
            return None
        resolved = (text.replace("${ProjectName}", project).replace("${AWS::AccountId}", account_id)
                    .replace("${AWS::Region}", region))
        return None if "${" in resolved else resolved


def aws_teardown() -> TeardownToolkit:
    return TeardownToolkit(inventory=CloudFormationInventory.default(),
                           notes=("CloudWatch Logs: not supported by AWS Backup",),
                           vault_pattern="cloudinfra-teardown-{region}",
                           unit_patterns=("{project}", BOOTSTRAP_STACK), missing_vault=NO_BACKUP_ACCOUNT)
