"""Turns the chosen control packs into the controls each node gets, with one cloud's mappings and inheritance."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from app.landing_zone.catalog.controls import CatalogControl
from app.landing_zone.catalog.mappings import ProviderControls
from app.landing_zone.catalog.packs import ControlPack, PackRegistry
from app.landing_zone.catalog.selectors import SelectorRegistry

if TYPE_CHECKING:  # the design imports the answers, which import the packs
    from app.landing_zone.design import LandingZoneDesign, OuNode


@dataclass(frozen=True)
class EnabledControl:
    control: CatalogControl
    parameters: dict[str, list[str]]
    packs: tuple[str, ...]


@dataclass
class ResolvedControls:
    controls: dict[str, list[EnabledControl]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


class Placements:
    """The controls being placed on each node, by node key and control id, before inheritance is applied."""

    def __init__(self):
        self.by_node: dict[str, dict[str, EnabledControl]] = {}

    def place(self, ou: OuNode, control: CatalogControl, pack_id: str, parameters: dict) -> None:
        on_ou = self.by_node.setdefault(ou.key, {})
        existing = on_ou.get(control.id)
        packs = (*existing.packs, pack_id) if existing else (pack_id,)
        on_ou[control.id] = EnabledControl(control, existing.parameters if existing else parameters, packs)


class PackResolver:
    """Each pack's controls, as the cloud maps them, go on the nodes its selectors choose. A control the cloud
    inherits down the hierarchy goes on the top-most targeted node only; others go on every targeted node (§20.12,
    §22.10.4)."""

    def __init__(self, packs: PackRegistry, controls: ProviderControls):
        self._packs = packs
        self._controls = controls
        self._selectors = SelectorRegistry()

    def resolve(self, design: LandingZoneDesign) -> ResolvedControls:
        answers = design.answers
        chosen = answers.control_packs if answers.control_packs is not None else self._packs.for_profile(
            answers.controls_profile)
        placements = Placements()
        result = ResolvedControls()
        for pack in map(self._packs.get, chosen):
            governed = self._governed(pack, design)
            if not governed:
                result.warnings.append(f"Control pack '{pack.name}' applies to no OU in this design.")
            for control in map(self._controls.snapshot.get, self._controls.mappings.controls_for(pack.id)):
                for ou in governed:
                    placements.place(ou, control, pack.id, self._parameters(design, pack, control))
        for prerequisite in self._controls.prerequisites:
            prerequisite.apply(placements, design, result)
        parents = {child.key: parent for parent in design.walk() for child in parent.children}
        on = placements.by_node
        result.controls = {ou.key: [enabled for enabled in on[ou.key].values()
                                    if not self._inherited(enabled, ou, parents, on)]
                           for ou in design.walk() if ou.key in on}
        return result

    def _governed(self, pack: ControlPack, design: LandingZoneDesign) -> list[OuNode]:
        """The selected OUs and every OU nested below them, once each, in tree order."""
        selected = {ou.key for name in pack.selectors for ou in self._selectors.get(name).select(design)}
        keys = selected | {nested.key for ou in design.walk() if ou.key in selected for nested in ou.descendants()}
        return [ou for ou in design.walk() if ou.key in keys]

    def _parameters(self, design: LandingZoneDesign, pack: ControlPack, control: CatalogControl) -> dict:
        chosen = design.answers.pack_parameters.get(pack.id, {})
        defaults = {"AllowedRegions": design.answers.governed_regions}
        return {name: chosen.get(name, defaults.get(name)) for name in control.parameters
                if name in chosen or name in defaults}

    def _inherited(self, enabled: EnabledControl, ou: OuNode, parents: dict, placements: dict) -> bool:
        """A control the cloud inherits, already enabled on an ancestor, reaches this node by inheritance."""
        if not self._controls.inheritance.inherited(enabled.control):
            return False
        ancestor = parents.get(ou.key)
        while ancestor is not None:
            if enabled.control.id in placements.get(ancestor.key, {}):
                return True
            ancestor = parents.get(ancestor.key)
        return False
