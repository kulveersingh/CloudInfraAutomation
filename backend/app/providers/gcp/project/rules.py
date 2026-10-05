from collections import Counter

from app.providers.gcp.project.capabilities import DUAL_REGION_LOCATIONS, FIRESTORE_MULTI_REGIONS, continent
from app.providers.gcp.project.dialect import CONTRACT
from app.synth.binders.kinds import EVENT_NOTIFY
from app.synth.binders.registry import BinderRegistry
from app.synth.blocks.registry import BlockRegistry
from app.synth.request import ProjectRequest
from app.synth.validation import RequestRule

STORAGE = "storage.bucket"
DATABASE = "database.table"


def spanning(request: ProjectRequest, blocks: BlockRegistry, type_name: str) -> list[str]:
    """Ids of the resources of a curated type that span both regions of a multi-region request."""
    if not request.resilience.is_multi_region or request.resilience.secondary_region is None:
        return []
    return [resource.id for resource in request.resources
            if blocks.has_type(resource.type) and blocks.block_class(resource.type).type_name == type_name]


class OneContinentRule(RequestRule):
    """Dual-region buckets and multi-region Firestore span regions of one continent only."""

    def __init__(self, blocks: BlockRegistry):
        self._blocks = blocks

    def messages(self, request):
        if not (spanning(request, self._blocks, STORAGE) or spanning(request, self._blocks, DATABASE)):
            return []
        resilience = request.resilience
        if continent(resilience.primary_region) == continent(resilience.secondary_region):
            return []
        return [("Google Cloud dual- and multi-region storage needs both regions on one continent "
                 f"({resilience.primary_region}, {resilience.secondary_region}).")]


class ReplicatedLocationRule(RequestRule):
    """A replicated service exists only in some continents (dual-region buckets: US, EU, Asia; Firestore: US, EU)."""

    def __init__(self, blocks: BlockRegistry, type_name: str, service: str, locations: dict[str, str]):
        self._blocks = blocks
        self._type_name = type_name
        self._service = service
        self._locations = locations

    def messages(self, request):
        where = continent(request.resilience.primary_region)
        if where in self._locations:
            return []
        return [f"{self._service} '{resource_id}' cannot span regions in {where}; it can in "
                f"{', '.join(sorted(self._locations))}." for resource_id in spanning(request, self._blocks, self._type_name)]


class ReservedIdRule(RequestRule):
    """Ids the platform gives its own resources in every configuration."""

    RESERVED = frozenset({CONTRACT})

    def messages(self, request):
        return [f"'{resource.id}' is reserved for the platform; choose another id." for resource in request.resources
                if resource.id in self.RESERVED]


class OneTriggerPerFunctionRule(RequestRule):
    """A Cloud Run function has a single event trigger."""

    def __init__(self, binders: BinderRegistry):
        self._binders = binders

    def messages(self, request):
        targets = Counter(connection.target for connection in request.connections
                          if self._binders.canonical(connection.kind) == EVENT_NOTIFY)
        return [f"'{target}' has {total} event triggers; a Cloud Run function takes one."
                for target, total in targets.items() if total > 1]


def gcp_rules(blocks: BlockRegistry, binders: BinderRegistry) -> list[RequestRule]:
    return [OneContinentRule(blocks),
            ReplicatedLocationRule(blocks, STORAGE, "Cloud Storage bucket", DUAL_REGION_LOCATIONS),
            ReplicatedLocationRule(blocks, DATABASE, "Firestore database", FIRESTORE_MULTI_REGIONS),
            OneTriggerPerFunctionRule(binders), ReservedIdRule()]
