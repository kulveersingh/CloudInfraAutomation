from abc import ABC, abstractmethod

from app.synth.access import SAME_TAG_RESOURCE_CONDITION, AccessActions
from app.synth.blocks.base import AccessTarget, Block
from app.synth.blocks.settings import TextSetting
from app.synth.policies import SameTagPolicy
from app.synth.template import Template

DEFAULT_PARTITION_KEY = "pk"
STRING_ATTRIBUTE = "S"
KEY_PATTERN = r"^[A-Za-z0-9_.-]{1,255}$"
KEY_RULE = "1 to 255 characters of letters, digits and _ . -"


class TableShape(ABC):
    """How a table is declared: a regional table, or a global table spanning the DR/HA pair."""

    def __init__(self, block: "DynamoDbTableBlock"):
        self._block = block

    def resource(self) -> dict:
        return {**self._header(), "Properties": {**self._block.common_properties(), **self._properties()},
                "DeletionPolicy": "RetainExceptOnCreate", "UpdateReplacePolicy": "Retain"}

    @abstractmethod
    def _header(self) -> dict:
        ...

    @abstractmethod
    def _properties(self) -> dict:
        ...


class RegionalTableShape(TableShape):
    def _header(self) -> dict:
        return {"Type": "AWS::DynamoDB::Table"}

    def _properties(self) -> dict:
        return {"PointInTimeRecoverySpecification": {"PointInTimeRecoveryEnabled": True},
                "SSESpecification": {"SSEEnabled": True},
                "ResourcePolicy": {"PolicyDocument": self._block.resource_policy()}}


class GlobalTableShape(TableShape):
    def _header(self) -> dict:
        return {"Type": "AWS::DynamoDB::GlobalTable", "Condition": "IsPrimary"}

    def _properties(self) -> dict:
        regions = self._block.request.resilience.selected_regions()
        return {"SSESpecification": {"SSEEnabled": True},
                "StreamSpecification": {"StreamViewType": "NEW_AND_OLD_IMAGES"},
                "Replicas": [self._replica(region) for region in regions]}

    def _replica(self, region: str) -> dict:
        return {"Region": region,
                "PointInTimeRecoverySpecification": {"PointInTimeRecoveryEnabled": True},
                "ResourcePolicy": {"PolicyDocument": self._block.resource_policy(region)}}


TABLE_SHAPES = {"single": RegionalTableShape, "dr": GlobalTableShape, "ha": GlobalTableShape}


class DynamoDbTableBlock(Block, AccessTarget):
    type_name = "dynamodb.table"
    display_name = "DynamoDB table"
    category = "Databases"
    multi_region = "global"
    logical_id_suffix = "Table"
    cloudformation_types = ("AWS::DynamoDB::Table", "AWS::DynamoDB::GlobalTable")
    settings = (
        TextSetting("partition_key", "Partition key", DEFAULT_PARTITION_KEY, KEY_PATTERN, KEY_RULE),
        TextSetting("sort_key", "Sort key", None, KEY_PATTERN, KEY_RULE, optional=True),
    )

    ACTIONS = AccessActions(
        read=["dynamodb:GetItem", "dynamodb:Query", "dynamodb:BatchGetItem"],
        write=["dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:DeleteItem", "dynamodb:BatchWriteItem"])

    def access_statements(self, access: str, prefix: str) -> list[dict]:
        table = self.naming.table_arn()
        return [{"Effect": "Allow", "Action": self.ACTIONS.for_level(access),
                 "Resource": [table, {"Fn::Sub": table["Fn::Sub"] + "/index/*"}],
                 "Condition": SAME_TAG_RESOURCE_CONDITION}]

    def environment_binding(self) -> tuple[str, object]:
        return self.naming.environment_variable("TABLE_NAME"), {"Fn::Sub": self.naming.physical_name()}

    def contract_entry(self) -> dict:
        return {"tableName": self.naming.physical_name()}

    def resource_policy(self, region: str = "${AWS::Region}") -> dict:
        return SameTagPolicy("dynamodb:*", [self.naming.table_arn(region)]).document()

    def common_properties(self) -> dict:
        keys = self._keys()
        return {"TableName": {"Fn::Sub": self.naming.physical_name()}, "BillingMode": "PAY_PER_REQUEST",
                "KeySchema": [{"AttributeName": name, "KeyType": key_type} for name, key_type in keys],
                "AttributeDefinitions": [{"AttributeName": name, "AttributeType": STRING_ATTRIBUTE}
                                         for name, _ in keys]}

    def emit(self, template: Template) -> None:
        template.add_resource(self.logical_id, TABLE_SHAPES[self.request.resilience.mode](self).resource())
        template.add_output(f"{self.logical_id}Name", {"Value": {"Fn::Sub": self.naming.physical_name()}})

    def _keys(self) -> list[tuple[str, str]]:
        partition = (self.setting("partition_key"), "HASH")
        sort_key = self.setting("sort_key")
        sort = [(sort_key, "RANGE")] if sort_key is not None else []
        return [partition, *sort]
