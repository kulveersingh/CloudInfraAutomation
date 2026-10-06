"""How one cloud implements the neutral control packs: its controls per pack, how they are inherited down the
hierarchy, and any controls they need first (§22.10.4)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from app.landing_zone.catalog.controls import CatalogControl, CatalogError, ControlCatalogSnapshot
from app.landing_zone.catalog.packs import PackRegistry

if TYPE_CHECKING:  # the design imports the answers, which import the packs
    from app.landing_zone.catalog.resolver import Placements, ResolvedControls
    from app.landing_zone.design import LandingZoneDesign


class PackMappings:
    """One cloud's control ids per pack, from one YAML file per pack (`pack`, `controls`)."""

    def __init__(self, controls: dict[str, tuple[str, ...]]):
        self._controls = controls

    @classmethod
    def load(cls, directory: Path, snapshot: ControlCatalogSnapshot, packs: PackRegistry) -> PackMappings:
        controls = {}
        for path in sorted(directory.glob("*.yaml")):
            document = yaml.safe_load(path.read_text())
            pack = packs.get(document["pack"]).id
            for control_id in document["controls"]:
                if control_id not in snapshot.controls:
                    raise CatalogError(f"Mapping of pack '{pack}' uses unknown control '{control_id}'.")
            controls[pack] = tuple(document["controls"])
        return cls(controls)

    def controls_for(self, pack_id: str) -> tuple[str, ...]:
        """The cloud's controls for a pack; none when the cloud has no equivalent."""
        return self._controls.get(pack_id, ())


class InheritanceRule(ABC):
    """Whether a control enabled on a node also governs the nodes below it."""

    @abstractmethod
    def inherited(self, control: CatalogControl) -> bool:
        ...


class PreventiveInherited(InheritanceRule):
    """Preventive policies flow down; detective and proactive controls must be enabled on each nested node."""

    def inherited(self, control):
        return control.is_preventive


class AllInherited(InheritanceRule):
    """Every control enabled on a node governs everything below it."""

    def inherited(self, control):
        return True


class ControlPrerequisite(ABC):
    """Controls a cloud needs before some of the resolved ones work; adds them, or warns."""

    @abstractmethod
    def apply(self, placements: Placements, design: LandingZoneDesign, result: ResolvedControls) -> None:
        ...


@dataclass(frozen=True)
class ProviderControls:
    """Everything the pack resolver needs from one cloud."""

    snapshot: ControlCatalogSnapshot
    mappings: PackMappings
    inheritance: InheritanceRule
    prerequisites: tuple[ControlPrerequisite, ...] = field(default=())
