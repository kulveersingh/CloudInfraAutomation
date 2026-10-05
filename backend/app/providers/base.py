from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, ClassVar

from app.errors import NotFoundError

if TYPE_CHECKING:
    from app.synth.toolkit import ProjectToolkit

DEFAULT_PROVIDER = "aws"


@dataclass(frozen=True)
class Vocabulary:
    """The words a cloud uses for the platform's neutral concepts (§22.2), so the UI speaks each cloud's language."""

    isolation_unit: str
    hierarchy_node: str
    iac_document: str
    deploy_unit: str
    preventive_policy: str
    private_network: str
    landing_zone_service: str
    control_catalog: str


class CloudProvider(ABC):
    """One cloud behind the platform's neutral core (§22.3). A new cloud is a new provider package, registered by id."""

    id: ClassVar[str]
    name: ClassVar[str]

    @abstractmethod
    def vocabulary(self) -> Vocabulary:
        ...

    @abstractmethod
    def default_regions(self) -> tuple[str, str]:
        """The primary and secondary region a new project starts with."""

    @abstractmethod
    def project(self) -> "ProjectToolkit":
        """Blocks, binders, IaC dialect, validation, linting and repository files for projects on this cloud."""

    def describe(self) -> dict:
        primary, secondary = self.default_regions()
        return {"id": self.id, "name": self.name, "vocabulary": asdict(self.vocabulary()),
                "default_regions": {"primary": primary, "secondary": secondary}}


class ProviderRegistry:
    def __init__(self):
        self._providers: dict[str, CloudProvider] = {}

    @classmethod
    def default(cls) -> "ProviderRegistry":
        from app.providers.aws.provider import AwsProvider

        registry = cls()
        registry.register(AwsProvider())
        return registry

    def register(self, provider: CloudProvider) -> None:
        self._providers[provider.id] = provider

    def has(self, provider_id: str) -> bool:
        return provider_id in self._providers

    def get(self, provider_id: str) -> CloudProvider:
        if provider_id not in self._providers:
            raise NotFoundError(unknown_provider(provider_id))
        return self._providers[provider_id]

    def all(self) -> list[CloudProvider]:
        return list(self._providers.values())


def unknown_provider(provider_id: str) -> str:
    return f"Unknown cloud provider '{provider_id}'."
