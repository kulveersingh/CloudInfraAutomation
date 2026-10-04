"""Which OUs a control pack targets. A new kind of target adds a selector to the registry."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:  # the design imports the answers, which import the packs and these selectors
    from app.landing_zone.design import LandingZoneDesign, OuNode

COMPLIANCE_PREFIX = "compliance:"


class OuSelector(ABC):
    @abstractmethod
    def select(self, design: LandingZoneDesign) -> list[OuNode]:
        ...


class IsolatedOus(OuSelector):
    """Every isolation boundary that holds workloads: environment OUs and root-level custom OUs."""

    def select(self, design):
        return design.isolated_ous()


class EnvironmentTier(OuSelector):
    def __init__(self, tier: str):
        self._tier = tier

    def select(self, design):
        return [ou for ou in design.environment_ous() if ou.tier == self._tier]


class OusOfKind(OuSelector):
    def __init__(self, kind: str):
        self._kind = kind

    def select(self, design):
        return [ou for ou in design.walk() if ou.kind == self._kind]


class ComplianceScope(OuSelector):
    """The scope's compliance OU; its STAGE and PROD children come with it (§20.12.3)."""

    def __init__(self, scope: str):
        self._key = scope.lower()

    def select(self, design):
        return [ou for ou in design.walk() if ou.kind == "compliance" and ou.key == self._key]


class SelectorRegistry:
    _SELECTORS: ClassVar[dict[str, OuSelector]] = {
        "workloads": IsolatedOus(),
        "production_tier": EnvironmentTier("prod"),
        "nonproduction_tier": EnvironmentTier("nonprod"),
        "sandbox": EnvironmentTier("sandbox"),
        "infrastructure": OusOfKind("infrastructure"),
        "custom_domains": OusOfKind("custom_domain"),
    }

    def knows(self, name: str) -> bool:
        return name.startswith(COMPLIANCE_PREFIX) or name in self._SELECTORS

    def get(self, name: str) -> OuSelector:
        if name.startswith(COMPLIANCE_PREFIX):
            return ComplianceScope(name.removeprefix(COMPLIANCE_PREFIX))
        return self._SELECTORS[name]
