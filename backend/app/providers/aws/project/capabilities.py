from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar

from app.providers.aws.project.naming import ResourceNaming
from app.providers.aws.project.template import Template
from app.synth.blocks.base import Block
from app.synth.request import ProjectRequest, ResourceSpec


class AwsBlock(Block, ABC):
    """An AWS service: CloudFormation logical ids, names and parameters."""

    logical_id_suffix: ClassVar[str] = ""

    def __init__(self, spec: ResourceSpec, request: ProjectRequest):
        super().__init__(spec, request)
        self.naming = ResourceNaming(spec.id)

    @property
    def logical_id(self) -> str:
        return self.naming.logical_id(self.logical_id_suffix)

    def required_parameters(self) -> dict:
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
