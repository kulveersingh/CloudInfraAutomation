from abc import ABC, abstractmethod

from app.providers.azure.project.naming import AzureNaming
from app.providers.azure.project.template import ArmDocuments
from app.synth.blocks.base import Block
from app.synth.request import ProjectRequest, ResourceSpec

LOCATION = "[parameters('location')]"
SECONDARY = "[parameters('secondaryLocation')]"
IDENTITY_API = "2023-01-31"
ROLE_API = "2022-04-01"
# What removing a service in the data stack does: the stack detaches it (MC4-2).
KEPT = "kept: detached from the data stack, delete it by hand"


def resource_id(type_name: str, *names: str) -> str:
    quoted = ", ".join(name if name.startswith("variables(") else f"'{name}'" for name in names)
    return f"resourceId('{type_name}', {quoted})"


def identity_id(identity: str) -> str:
    return resource_id("Microsoft.ManagedIdentity/userAssignedIdentities", identity)


def principal_of(identity: str) -> str:
    return f"[reference({identity_id(identity)}, '{IDENTITY_API}').principalId]"


def role_assignment(scope: str, role: str, principal: str, comment: str, depends: list[str],
                    condition: str | None = None) -> dict:
    properties = {"roleDefinitionId": f"[subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '{role}')]",
                  "principalId": principal, "principalType": "ServicePrincipal"}
    if condition:
        properties.update({"condition": condition, "conditionVersion": "2.0"})
    return {"type": "Microsoft.Authorization/roleAssignments", "apiVersion": ROLE_API, "comments": comment,
            "name": f"[guid(resourceGroup().id, '{comment}', '{role}')]", "scope": scope, "properties": properties,
            "dependsOn": depends}


class AzureBlock(Block, ABC):
    """An Azure service. Each declares its names as variables in every stack, so any can refer to them."""

    def __init__(self, spec: ResourceSpec, request: ProjectRequest):
        super().__init__(spec, request)
        self.naming = AzureNaming(request.project_name, spec.id)

    @property
    def spans_regions(self) -> bool:
        return self.request.resilience.is_multi_region

    @property
    def attached(self) -> bool:
        return self.request.network.attach_compute

    def declare(self, documents: ArmDocuments, name: str, value: str) -> None:
        for template in documents.all():
            template.set_variable(name, value)

    @abstractmethod
    def emit(self, documents: ArmDocuments) -> None:
        ...


class GrantTarget(ABC):
    """A resource a workload's identity can be given a role on, scoped to exactly that resource."""

    @abstractmethod
    def grants(self, access: str, prefix: str, identity: str, comment: str) -> list[dict]:
        """The role assignments, in the shared stack: removing the connection deletes them."""

    @abstractmethod
    def environment(self) -> dict[str, str]:
        ...


class Workload(ABC):
    """Code that runs with its own user-assigned identity, gets app settings and Event Grid subscriptions."""

    @abstractmethod
    def identity(self) -> str:
        ...

    @abstractmethod
    def add_environment(self, variables: dict[str, str]) -> None:
        ...

    @abstractmethod
    def add_subscription(self, source: "EventSource", prefix: str, suffix: str) -> None:
        ...


class EventSource(ABC):
    """A resource whose events Event Grid delivers to functions."""

    @abstractmethod
    def topic(self) -> str:
        """The Event Grid system topic's name expression (without brackets)."""

    @abstractmethod
    def event_filter(self, prefix: str, suffix: str) -> dict:
        ...

    @abstractmethod
    def read_grant(self, identity: str, comment: str) -> dict:
        ...
