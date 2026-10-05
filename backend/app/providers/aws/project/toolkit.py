from functools import cache

from app.providers.aws.project.binders.event_notify import EventNotifyBinder
from app.providers.aws.project.binders.iam_access import IamAccessBinder
from app.providers.aws.project.blocks.cloudformation import (
    CloudFormationSchemaCatalog,
    SchemaDrivenBlockResolver,
)
from app.providers.aws.project.blocks.dynamodb_table import DynamoDbTableBlock
from app.providers.aws.project.blocks.lambda_function import LambdaFunctionBlock
from app.providers.aws.project.blocks.s3_bucket import S3BucketBlock
from app.providers.aws.project.blocks.sqs_queue import SqsQueueBlock
from app.providers.aws.project.dialect import CloudFormationDialect
from app.providers.aws.project.lint import aws_linter
from app.providers.aws.project.render import aws_bundle
from app.providers.aws.project.variables import AwsEnvironmentVariables
from app.synth.binders.registry import BinderRegistry
from app.synth.blocks.registry import BlockRegistry
from app.synth.synthesizer import TemplateSynthesizer
from app.synth.toolkit import ProjectToolkit
from app.synth.validation import RequestValidator

CURATED_BLOCKS = (S3BucketBlock, LambdaFunctionBlock, DynamoDbTableBlock, SqsQueueBlock)
BINDERS = (EventNotifyBinder(), IamAccessBinder())


def aws_blocks() -> BlockRegistry:
    registry = BlockRegistry()
    for block_class in CURATED_BLOCKS:
        registry.register(block_class, block_class.aliases)
    registry.register_resolver(SchemaDrivenBlockResolver(CloudFormationSchemaCatalog.bundled()))
    return registry


def aws_binders() -> BinderRegistry:
    registry = BinderRegistry()
    for binder in BINDERS:
        registry.register(binder, getattr(binder, "aliases", ()))
    return registry


def aws_synthesizer() -> TemplateSynthesizer:
    return TemplateSynthesizer(aws_blocks(), aws_binders(), CloudFormationDialect())


@cache
def aws_project() -> ProjectToolkit:
    """AWS's project toolkit, built once (the CloudFormation schema catalog is large)."""
    blocks, binders = aws_blocks(), aws_binders()
    return ProjectToolkit(blocks=blocks, binders=binders,
                          synthesizer=TemplateSynthesizer(blocks, binders, CloudFormationDialect()),
                          validator=RequestValidator.default(blocks, binders), linter=aws_linter(),
                          bundle=aws_bundle(), types=CloudFormationSchemaCatalog.bundled(),
                          variables=AwsEnvironmentVariables())
