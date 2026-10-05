from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.synth.binders.registry import BinderRegistry
from app.synth.blocks.registry import BlockRegistry
from app.synth.catalog import ServiceCatalog
from app.synth.lint import TemplateLinter
from app.synth.render import RepositoryBundle
from app.synth.synthesizer import TemplateSynthesizer
from app.synth.validation import RequestValidator

SEARCH_LIMIT = 50


class ResourceTypeCatalog(ABC):
    """Every raw resource type a provider publishes, for the Tier-2 search (§6.8)."""

    @abstractmethod
    def search(self, text: str, limit: int = SEARCH_LIMIT) -> list[dict]:
        ...


class WorkflowVariables(ABC):
    """The GitHub environment variables a provider's deploy workflow reads, per environment."""

    @abstractmethod
    def for_environment(self, context, environment: str) -> dict[str, str]:
        """`context` is the provisioning context: accounts, topology, bootstrap outputs and networks."""


@dataclass(frozen=True)
class ProjectToolkit:
    """What a provider gives the core to generate a project's repository (§22.3)."""

    blocks: BlockRegistry
    binders: BinderRegistry
    synthesizer: TemplateSynthesizer
    validator: RequestValidator
    linter: TemplateLinter
    bundle: RepositoryBundle
    types: ResourceTypeCatalog
    variables: WorkflowVariables

    def catalog(self) -> list[dict]:
        return ServiceCatalog(self.blocks).entries()
