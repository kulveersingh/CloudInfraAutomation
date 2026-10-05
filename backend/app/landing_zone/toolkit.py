from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.landing_zone.design import LandingZoneDesign, OrgCatalog
from app.landing_zone.validation import DesignWarning


class LandingZoneCheck(ABC):
    """A limit or rule of one cloud that a design must respect before it can be submitted."""

    @abstractmethod
    def problems(self, design: LandingZoneDesign, catalog: OrgCatalog) -> list[str]:
        ...


class LandingZoneRenderer(ABC):
    """Renders the landing-zone repository: the cloud's IaC, design.json, diagrams, scripts and workflow."""

    @abstractmethod
    def render(self, design: LandingZoneDesign, catalog: OrgCatalog) -> dict[str, str]:
        ...


@dataclass(frozen=True)
class LandingZoneToolkit:
    """What a provider gives the landing-zone workflow (§22.3): its repository, renderer, limits and advice."""

    repository_name: str
    bundle: LandingZoneRenderer
    checks: tuple[LandingZoneCheck, ...]
    advice: tuple[DesignWarning, ...]
