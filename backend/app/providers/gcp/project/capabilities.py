from abc import ABC, abstractmethod

from app.providers.gcp.project.document import PRIMARY_ONLY, TerraformDocument
from app.providers.gcp.project.naming import GcpNaming
from app.synth.blocks.base import Block
from app.synth.request import ProjectRequest, ResourceSpec

# Dual-region storage and multi-region Firestore exist only within these continents.
DUAL_REGION_LOCATIONS = {"us": "US", "europe": "EU", "asia": "ASIA"}
FIRESTORE_MULTI_REGIONS = {"us": "nam5", "europe": "eur3"}


def continent(region: str) -> str:
    return region.split("-")[0]


class GcpBlock(Block, ABC):
    """A Google Cloud service. Project-wide resources (service accounts, dual-region buckets, multi-region
    databases, topics) are created once, by the primary region's deployment."""

    def __init__(self, spec: ResourceSpec, request: ProjectRequest):
        super().__init__(spec, request)
        self.naming = GcpNaming(request.project_name, spec.id)

    @property
    def spans_regions(self) -> bool:
        return self.request.resilience.is_multi_region

    def primary_only(self, body: dict) -> dict:
        return {"count": PRIMARY_ONLY, **body} if self.spans_regions else body

    @property
    def main_resource(self) -> tuple[str, str]:
        """(type, name) of the resource that is the service itself, e.g. the bucket rather than its bindings."""
        return self.provider_types[0], self.spec.id

    def reference(self, type_name: str, name: str, attribute: str) -> str:
        """An attribute of one of this block's resources, indexed when the resource is primary-only."""
        return f"${{{type_name}.{name}{'[0]' if self.spans_regions else ''}.{attribute}}}"

    def required_variables(self) -> dict:
        return {}

    @abstractmethod
    def emit(self, document: TerraformDocument) -> None:
        ...


class GrantTarget(ABC):
    """A resource a workload can be granted access to, bound on the resource itself."""

    @abstractmethod
    def grants(self, access: str, prefix: str, member: str, source_id: str) -> list[tuple[str, str, dict]]:
        """(resource type, name, body) of each IAM binding."""

    @abstractmethod
    def environment(self) -> dict[str, str]:
        """The names a workload needs in its environment to reach this resource."""


class Workload(ABC):
    """Code that runs as its own service account: it receives bindings, environment variables and triggers."""

    @abstractmethod
    def member(self) -> str:
        ...

    @abstractmethod
    def add_environment(self, variables: dict[str, str]) -> None:
        ...

    @abstractmethod
    def add_trigger(self, trigger: dict) -> None:
        ...


class EventSource(ABC):
    """A resource whose events can trigger a workload through Eventarc."""

    @abstractmethod
    def event_trigger(self) -> dict:
        ...

    @abstractmethod
    def read_grant(self, member: str, source_id: str) -> tuple[str, str, dict]:
        ...
