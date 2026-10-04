from abc import ABC, abstractmethod
from collections import Counter

from app.synth.access import WRITE_LEVELS
from app.synth.binders.event_notify import EventNotifyBinder
from app.synth.binders.iam_access import IamAccessBinder
from app.synth.binders.registry import BinderRegistry
from app.synth.blocks.registry import BlockRegistry
from app.synth.request import ConnectionSpec, ProjectRequest


class RequestValidationError(Exception):
    def __init__(self, messages: list[str]):
        super().__init__("; ".join(messages))
        self.messages = list(messages)


class RequestRule(ABC):
    """One semantic check on a project request. Add rules to RequestValidator to extend validation."""

    @abstractmethod
    def messages(self, request: ProjectRequest) -> list[str]:
        ...


class UniqueResourceIdsRule(RequestRule):
    def messages(self, request):
        counts = Counter(resource.id for resource in request.resources)
        return [f"Duplicate resource id '{resource_id}'." for resource_id, total in counts.items() if total > 1]


class KnownResourceTypesRule(RequestRule):
    def __init__(self, blocks: BlockRegistry):
        self._blocks = blocks

    def messages(self, request):
        return [f"Unknown resource type '{resource.type}' for '{resource.id}'."
                for resource in request.resources if not self._blocks.has_type(resource.type)]


class ConnectionEndpointsRule(RequestRule):
    def messages(self, request):
        return [f"Connection refers to unknown resource '{endpoint}'."
                for connection in request.connections for endpoint in (connection.source, connection.target)
                if request.resource(endpoint) is None]


class ConnectionCompatibilityRule(RequestRule):
    def __init__(self, blocks: BlockRegistry, binders: BinderRegistry):
        self._blocks = blocks
        self._binders = binders

    def messages(self, request):
        return [message for connection in request.connections for message in self._check(request, connection)]

    def _check(self, request: ProjectRequest, connection: ConnectionSpec) -> list[str]:
        if not self._binders.has_kind(connection.kind):
            return [f"Unknown connection kind '{connection.kind}'."]
        endpoints = [request.resource(connection.source), request.resource(connection.target)]
        if not all(endpoint and self._blocks.has_type(endpoint.type) for endpoint in endpoints):
            return []
        source_type, target_type = (self._blocks.block_class(endpoint.type) for endpoint in endpoints)
        return self._binders.binder(connection.kind).problems(connection, source_type, target_type)


class ResilienceRegionsRule(RequestRule):
    def messages(self, request):
        resilience = request.resilience
        if not resilience.is_multi_region:
            return []
        if resilience.secondary_region is None:
            return [f"A {resilience.mode} project needs a secondary region."]
        if resilience.secondary_region == resilience.primary_region:
            return ["Primary and secondary regions must be different."]
        return []


class BlockNamingRule(RequestRule):
    def __init__(self, blocks: BlockRegistry):
        self._blocks = blocks

    def messages(self, request):
        return [message for resource in request.resources if self._blocks.has_type(resource.type)
                for message in self._blocks.block_class(resource.type).naming_problems(request.project_name,
                                                                                      resource.id)]


class RecursiveInvocationRule(RequestRule):
    def messages(self, request):
        writes = [connection for connection in request.connections
                  if connection.kind == IamAccessBinder.kind and connection.access in WRITE_LEVELS]
        return [self._message(write) for write in writes if self._triggers_writer(request, write)]

    def _triggers_writer(self, request: ProjectRequest, write: ConnectionSpec) -> bool:
        return any(connection.kind == EventNotifyBinder.kind and connection.source == write.target
                   and connection.target == write.source and self._overlap(connection.prefix, write.prefix)
                   for connection in request.connections)

    def _overlap(self, first: str, second: str) -> bool:
        return first.startswith(second) or second.startswith(first)

    def _message(self, write: ConnectionSpec) -> str:
        return (f"'{write.source}' writes to '{write.target}' where it is triggered: "
                "this would invoke itself recursively.")


class RequestValidator:
    def __init__(self, rules: list[RequestRule]):
        self._rules = rules

    @classmethod
    def default(cls, blocks: BlockRegistry, binders: BinderRegistry) -> "RequestValidator":
        return cls([UniqueResourceIdsRule(), KnownResourceTypesRule(blocks), ConnectionEndpointsRule(),
                    ConnectionCompatibilityRule(blocks, binders), ResilienceRegionsRule(), BlockNamingRule(blocks),
                    RecursiveInvocationRule()])

    def validate(self, request: ProjectRequest) -> None:
        messages = [message for rule in self._rules for message in rule.messages(request)]
        if messages:
            raise RequestValidationError(messages)
