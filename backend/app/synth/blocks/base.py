from abc import ABC, abstractmethod
from typing import ClassVar

from app.synth.blocks.settings import Setting
from app.synth.request import ProjectRequest, ResourceSpec


class Block(ABC):
    """One catalog service of one cloud. Providers implement it per neutral kind and register it in BlockRegistry."""

    type_name: ClassVar[str]
    display_name: ClassVar[str]
    category: ClassVar[str]
    multi_region: ClassVar[str]
    # The provider's own resource types this block stands for; requesting one of them directly is refused.
    provider_types: ClassVar[tuple[str, ...]] = ()
    settings: ClassVar[tuple[Setting, ...]] = ()
    # Whether removing the service keeps its data (a retain policy) or deletes it on the next deploy.
    retained_on_removal: ClassVar[bool] = False

    def __init__(self, spec: ResourceSpec, request: ProjectRequest):
        self.spec = spec
        self.request = request

    @classmethod
    def naming_problems(cls, project_name: str, resource_id: str) -> list[str]:
        return []

    @classmethod
    def config_problems(cls, spec: ResourceSpec) -> list[str]:
        declared = {setting.name: setting for setting in cls.settings}
        subject = f"{spec.type} '{spec.id}'"
        problems = []
        for key, value in spec.config.items():
            if key not in declared:
                problems.append(f"{subject} does not accept '{key}'; {cls._allowed_settings()}.")
            else:
                problems += [f"{subject} setting '{key}' {reason}." for reason in declared[key].problems(value)]
        return problems

    @classmethod
    def _allowed_settings(cls) -> str:
        names = [setting.name for setting in cls.settings]
        return f"allowed: {', '.join(names)}" if names else "it has no settings"

    def setting(self, name: str):
        """The value the request chose, or the declared default."""
        declared = next(setting for setting in self.settings if setting.name == name)
        return self.spec.config.get(name, declared.default)

    @property
    def uses_network(self) -> bool:
        return False

    def contract_entry(self) -> dict:
        return {}

    @abstractmethod
    def emit(self, document) -> None:
        """Adds this service's resources to the provider's IaC document."""
