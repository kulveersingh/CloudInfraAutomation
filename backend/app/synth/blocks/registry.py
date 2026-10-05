from typing import Protocol

from app.synth.blocks.base import Block
from app.synth.blocks.cloudformation import CloudFormationSchemaCatalog, SchemaDrivenBlockResolver
from app.synth.blocks.dynamodb_table import DynamoDbTableBlock
from app.synth.blocks.lambda_function import LambdaFunctionBlock
from app.synth.blocks.s3_bucket import S3BucketBlock
from app.synth.blocks.sqs_queue import SqsQueueBlock
from app.synth.request import ProjectRequest, ResourceSpec

DEFAULT_BLOCKS = (S3BucketBlock, LambdaFunctionBlock, DynamoDbTableBlock, SqsQueueBlock)


class UnknownBlockTypeError(KeyError):
    pass


class BlockResolver(Protocol):
    """Supplies block classes for whole families of types (e.g. every CloudFormation resource type)."""

    def claims(self, type_name: str) -> bool: ...

    def supports(self, type_name: str) -> bool: ...

    def block_class(self, type_name: str) -> type[Block]: ...

    def problems_for(self, resource: ResourceSpec) -> list[str]: ...


class BlockRegistry:
    """Maps type names to block classes: curated blocks first, then resolvers. Extend with register*()."""

    def __init__(self):
        self._classes: dict[str, type[Block]] = {}
        self._resolvers: list[BlockResolver] = []

    @classmethod
    def default(cls) -> "BlockRegistry":
        registry = cls()
        for block_class in DEFAULT_BLOCKS:
            registry.register(block_class)
        registry.register_resolver(SchemaDrivenBlockResolver(CloudFormationSchemaCatalog.bundled()))
        return registry

    def register(self, block_class: type[Block]) -> None:
        self._classes[block_class.type_name] = block_class

    def register_resolver(self, resolver: BlockResolver) -> None:
        self._resolvers.append(resolver)

    def has_type(self, type_name: str) -> bool:
        if type_name in self._classes:
            return True
        return self._curated_alias(type_name) is None and any(
            resolver.supports(type_name) for resolver in self._resolvers)

    def block_class(self, type_name: str) -> type[Block]:
        if not self.has_type(type_name):
            raise UnknownBlockTypeError(type_name)
        if type_name in self._classes:
            return self._classes[type_name]
        return next(resolver for resolver in self._resolvers if resolver.supports(type_name)).block_class(type_name)

    def problems_for(self, resource: ResourceSpec) -> list[str]:
        if resource.type in self._classes:
            return self._classes[resource.type].config_problems(resource)
        alias = self._curated_alias(resource.type)
        if alias is not None:
            return [f"Use the curated service '{alias}' instead of '{resource.type}' for '{resource.id}'."]
        claiming = [resolver for resolver in self._resolvers if resolver.claims(resource.type)]
        if not claiming:
            return [f"Unknown resource type '{resource.type}' for '{resource.id}'."]
        return claiming[0].problems_for(resource)

    def create(self, spec: ResourceSpec, request: ProjectRequest) -> Block:
        return self.block_class(spec.type)(spec, request)

    def type_names(self) -> list[str]:
        return sorted(self._classes)

    def classes(self) -> list[type[Block]]:
        return [self._classes[type_name] for type_name in self.type_names()]

    def _curated_alias(self, type_name: str) -> str | None:
        return next((block_class.type_name for block_class in self._classes.values()
                     if type_name in block_class.cloudformation_types), None)
