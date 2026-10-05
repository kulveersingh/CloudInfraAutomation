from functools import cache

from app.providers.gcp.project.binders.access_grant import ResourceBindingBinder
from app.providers.gcp.project.binders.event_notify import EventarcBinder
from app.providers.gcp.project.blocks.firestore import FirestoreDatabaseBlock
from app.providers.gcp.project.blocks.function import CloudRunFunctionBlock
from app.providers.gcp.project.blocks.pubsub_queue import PubSubQueueBlock
from app.providers.gcp.project.blocks.raw import RawResourceResolver
from app.providers.gcp.project.blocks.storage_bucket import CloudStorageBucketBlock
from app.providers.gcp.project.dialect import TerraformJsonDialect
from app.providers.gcp.project.lint import gcp_linter
from app.providers.gcp.project.notes import EventFilterAdvisor
from app.providers.gcp.project.render import gcp_bundle
from app.providers.gcp.project.rules import gcp_rules
from app.providers.gcp.project.schema import GoogleProviderSchema
from app.providers.gcp.project.variables import GcpEnvironmentVariables
from app.synth.binders.registry import BinderRegistry
from app.synth.blocks.registry import BlockRegistry
from app.synth.synthesizer import TemplateSynthesizer
from app.synth.toolkit import ProjectToolkit
from app.synth.validation import RequestValidator

CURATED_BLOCKS = (CloudStorageBucketBlock, CloudRunFunctionBlock, FirestoreDatabaseBlock, PubSubQueueBlock)
BINDERS = (EventarcBinder(), ResourceBindingBinder())


def gcp_blocks() -> BlockRegistry:
    registry = BlockRegistry()
    for block_class in CURATED_BLOCKS:
        registry.register(block_class)
    registry.register_resolver(RawResourceResolver(GoogleProviderSchema.bundled()))
    return registry


def gcp_binders() -> BinderRegistry:
    registry = BinderRegistry()
    for binder in BINDERS:
        registry.register(binder, getattr(binder, "aliases", ()))
    return registry


@cache
def gcp_project() -> ProjectToolkit:
    """Google Cloud's project toolkit, built once (the provider schema is large)."""
    blocks, binders = gcp_blocks(), gcp_binders()
    default = RequestValidator.default(blocks, binders)
    return ProjectToolkit(blocks=blocks, binders=binders,
                          synthesizer=TemplateSynthesizer(blocks, binders, TerraformJsonDialect()),
                          validator=RequestValidator([*default.rules, *gcp_rules(blocks, binders)]),
                          linter=gcp_linter(), bundle=gcp_bundle(), types=GoogleProviderSchema.bundled(),
                          variables=GcpEnvironmentVariables(), advisor=EventFilterAdvisor(binders))
