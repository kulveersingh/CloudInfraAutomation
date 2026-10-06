from abc import ABC, abstractmethod
from dataclasses import dataclass, field, replace

from app.landing_zone.design import AccountPlan


class UnitNamer(ABC):
    """Names the isolation units (accounts, projects) a landing zone vends, the cloud's way (§22.10.3)."""

    @abstractmethod
    def unit(self, suffix: str) -> AccountPlan:
        ...

    def fixed(self, suffix: str) -> AccountPlan:
        """A unit that one questionnaire answer decides; the tree editor leaves it alone."""
        return replace(self.unit(suffix), fixed=True)

    def added(self, suffix: str) -> AccountPlan:
        """A unit the tree editor added; it can be removed again."""
        return replace(self.unit(suffix), added=True)


@dataclass(frozen=True)
class UnitCatalog:
    """The units a cloud's landing zone always vends (§22.10.2): the Security node's, the shared ones per
    Infrastructure answer, a network host per workload environment where the cloud has one, and the nodes the
    cloud's own landing-zone service creates."""

    security: tuple[str, ...]
    security_tooling: str
    infrastructure: dict[str, str]  # Infrastructure answer → unit suffix; answers the cloud has no unit for are absent
    environment_host: str | None = None  # e.g. "net-{environment}", a Shared VPC host project per environment
    created_by_service: frozenset[str] = field(default_factory=frozenset)  # "security", "sandbox"

    def host_for(self, environment_name: str) -> str | None:
        return self.environment_host.format(environment=environment_name.lower()) if self.environment_host else None
