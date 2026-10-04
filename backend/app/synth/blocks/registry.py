from app.synth.blocks.base import Block
from app.synth.blocks.dynamodb_table import DynamoDbTableBlock
from app.synth.blocks.lambda_function import LambdaFunctionBlock
from app.synth.blocks.s3_bucket import S3BucketBlock
from app.synth.blocks.sqs_queue import SqsQueueBlock
from app.synth.request import ProjectRequest, ResourceSpec

DEFAULT_BLOCKS = (S3BucketBlock, LambdaFunctionBlock, DynamoDbTableBlock, SqsQueueBlock)


class UnknownBlockTypeError(KeyError):
    pass


class BlockRegistry:
    """Maps catalog type names to block classes. New services are added with register()."""

    def __init__(self):
        self._classes: dict[str, type[Block]] = {}

    @classmethod
    def default(cls) -> "BlockRegistry":
        registry = cls()
        for block_class in DEFAULT_BLOCKS:
            registry.register(block_class)
        return registry

    def register(self, block_class: type[Block]) -> None:
        self._classes[block_class.type_name] = block_class

    def has_type(self, type_name: str) -> bool:
        return type_name in self._classes

    def block_class(self, type_name: str) -> type[Block]:
        try:
            return self._classes[type_name]
        except KeyError:
            raise UnknownBlockTypeError(type_name) from None

    def create(self, spec: ResourceSpec, request: ProjectRequest) -> Block:
        return self.block_class(spec.type)(spec, request)

    def type_names(self) -> list[str]:
        return sorted(self._classes)

    def classes(self) -> list[type[Block]]:
        return [self._classes[type_name] for type_name in self.type_names()]
