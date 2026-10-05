from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar

from app.synth.blocks.settings import Setting
from app.synth.naming import ResourceNaming
from app.synth.request import ProjectRequest, ResourceSpec
from app.synth.template import Template


class Block(ABC):
    """One catalog service. Subclasses emit its CloudFormation resources; register them in BlockRegistry."""

    type_name: ClassVar[str]
    display_name: ClassVar[str]
    category: ClassVar[str]
    multi_region: ClassVar[str]
    logical_id_suffix: ClassVar[str] = ""
    cloudformation_types: ClassVar[tuple[str, ...]] = ()
    settings: ClassVar[tuple[Setting, ...]] = ()

    def __init__(self, spec: ResourceSpec, request: ProjectRequest):
        self.spec = spec
        self.request = request
        self.naming = ResourceNaming(spec.id)

    @property
    def logical_id(self) -> str:
        return self.naming.logical_id(self.logical_id_suffix)

    @classmethod
    def naming_problems(cls, project_name: str, resource_id: str) -> list[str]:
        return []

    @classmethod
    def config_problems(cls, spec: ResourceSpec) -> list[str]:
        declared = {setting.name: setting for setting in cls.settings}
        subject = f"{cls.type_name} '{spec.id}'"
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

    def required_parameters(self) -> dict:
        return {}

    def contract_entry(self) -> dict:
        return {}

    @abstractmethod
    def emit(self, template: Template) -> None:
        ...


class AccessTarget(ABC):
    """A resource that runtime principals can be granted access to."""

    @abstractmethod
    def access_statements(self, access: str, prefix: str) -> list[dict]:
        ...

    @abstractmethod
    def environment_binding(self) -> tuple[str, object]:
        ...


class RuntimePrincipal(ABC):
    """A component that runs code with its own role: it receives grants and environment variables."""

    @abstractmethod
    def grant(self, statement: dict) -> None:
        ...

    @abstractmethod
    def bind_environment(self, name: str, value: object) -> None:
        ...


class InvocableFunction(ABC):
    """A function that AWS services can invoke."""

    @abstractmethod
    def arn(self) -> dict:
        ...


@dataclass(frozen=True)
class FunctionNotification:
    events: list[str]
    function_arn: dict
    prefix: str
    suffix: str
    permission_id: str


class NotificationSource(ABC):
    """A resource that pushes events to functions."""

    notification_principal: ClassVar[str]

    @abstractmethod
    def add_notification(self, notification: FunctionNotification) -> None:
        ...

    @abstractmethod
    def source_arn(self) -> dict:
        ...

    @abstractmethod
    def notification_read_statement(self, prefix: str) -> dict:
        ...
