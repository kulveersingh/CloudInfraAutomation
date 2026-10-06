from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass

from pydantic import BaseModel

from app.landing_zone.answers import LandingZoneAnswers
from app.landing_zone.catalog.mappings import ProviderControls
from app.landing_zone.catalog.packs import PackRegistry
from app.landing_zone.catalog.resolver import PackResolver
from app.landing_zone.design import LandingZoneDesign, OrgCatalog
from app.landing_zone.designer import LandingZoneDesigner, NamerFactory
from app.landing_zone.naming import UnitCatalog
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
    """What a provider gives the landing-zone workflow (§22.3, §22.10): its repository, renderer, limits and advice;
    the model of its own answers, how it names units, how it implements the control packs, placeholder answers to
    preview templates with, and what the diagram says about the organization root."""

    repository_name: str
    bundle: LandingZoneRenderer
    checks: tuple[LandingZoneCheck, ...]
    advice: tuple[DesignWarning, ...]
    answers: type[BaseModel]
    namer: NamerFactory
    controls: ProviderControls
    preview_answers: dict
    root_detail: Callable[[LandingZoneAnswers], list[str]]
    units: UnitCatalog

    def designer(self) -> LandingZoneDesigner:
        return LandingZoneDesigner.default(self.namer, self.units)

    def resolver(self) -> PackResolver:
        return PackResolver(PackRegistry.default(), self.controls)
