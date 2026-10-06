from functools import cache

from app.providers.azure.project.binders.access_grant import RoleAssignmentBinder
from app.providers.azure.project.binders.event_notify import EventGridBinder
from app.providers.azure.project.blocks.cosmos import CosmosContainerBlock
from app.providers.azure.project.blocks.function_app import FlexFunctionBlock
from app.providers.azure.project.blocks.raw import RawResourceResolver
from app.providers.azure.project.blocks.service_bus import ServiceBusQueueBlock
from app.providers.azure.project.blocks.storage_account import StorageAccountBlock
from app.providers.azure.project.dialect import ArmTemplateDialect
from app.providers.azure.project.lint import azure_linter
from app.providers.azure.project.render import azure_bundle
from app.providers.azure.project.rules import PairedRegionRule
from app.providers.azure.project.schema import AzureResourceTypes
from app.providers.azure.project.variables import AzureEnvironmentVariables
from app.synth.binders.registry import BinderRegistry
from app.synth.blocks.registry import BlockRegistry
from app.synth.synthesizer import TemplateSynthesizer
from app.synth.toolkit import ProjectToolkit
from app.synth.validation import RequestValidator

CURATED_BLOCKS = (StorageAccountBlock, FlexFunctionBlock, CosmosContainerBlock, ServiceBusQueueBlock)
BINDERS = (EventGridBinder(), RoleAssignmentBinder())


@cache
def azure_project(pairs) -> ProjectToolkit:
    """Azure's project toolkit, built once. `pairs` gives a region's fixed pair."""
    types = AzureResourceTypes.bundled()
    blocks = BlockRegistry()
    for block_class in CURATED_BLOCKS:
        blocks.register(block_class)
    blocks.register_resolver(RawResourceResolver(types))
    binders = BinderRegistry()
    for binder in BINDERS:
        binders.register(binder, getattr(binder, "aliases", ()))
    default = RequestValidator.default(blocks, binders)
    return ProjectToolkit(blocks=blocks, binders=binders,
                          synthesizer=TemplateSynthesizer(blocks, binders, ArmTemplateDialect(types)),
                          validator=RequestValidator([*default.rules, PairedRegionRule(blocks, pairs)]),
                          linter=azure_linter(), bundle=azure_bundle(), types=types,
                          variables=AzureEnvironmentVariables())
