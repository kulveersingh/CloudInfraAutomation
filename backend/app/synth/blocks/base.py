from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar

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
