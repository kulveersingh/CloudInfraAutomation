"""Turns the chosen control packs into the Control Tower controls each OU gets."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from app.landing_zone.catalog.controls import CatalogControl, ControlCatalogSnapshot
from app.landing_zone.catalog.packs import ControlPack, PackRegistry
from app.landing_zone.catalog.selectors import SelectorRegistry

if TYPE_CHECKING:  # the design imports the answers, which import the packs
    from app.landing_zone.design import LandingZoneDesign, OuNode

HOOKS_PREREQUISITE_PACK = "cloudformation-hooks"
UNRESOLVED_PREREQUISITE = ("Proactive controls need the CloudFormation-hooks prerequisite control (CT.CLOUDFORMATION.PR.1). "
                           "Refresh the control catalog to resolve its identifier.")


@dataclass(frozen=True)
class EnabledControl:
    control: CatalogControl
    parameters: dict[str, list[str]]
    packs: tuple[str, ...]


@dataclass
class ResolvedControls:
    controls: dict[str, list[EnabledControl]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


class PackResolver:
    """Preventive controls go on the top-most targeted OU, because SCPs, RCPs and declarative policies flow down.
    Detective and proactive controls are not inherited by nested OUs, so they go on every targeted OU (§20.12)."""

    def __init__(self, packs: PackRegistry, snapshot: ControlCatalogSnapshot):
        self._packs = packs
        self._snapshot = snapshot
        self._selectors = SelectorRegistry()

    @classmethod
    def default(cls) -> PackResolver:
        return cls(PackRegistry.default(), ControlCatalogSnapshot.default())

    def resolve(self, design: LandingZoneDesign) -> ResolvedControls:
        answers = design.answers
        chosen = answers.control_packs if answers.control_packs is not None else self._packs.for_profile(
            answers.controls_profile)
        placements: dict[str, dict[str, EnabledControl]] = {}
        result = ResolvedControls()
        for pack in map(self._packs.get, chosen):
            governed = self._governed(pack, design)
            if not governed:
                result.warnings.append(f"Control pack '{pack.name}' applies to no OU in this design.")
            for control in map(self._snapshot.get, pack.control_ids):
                for ou in governed:
                    self._place(placements, ou, control, pack.id, self._parameters(design, pack, control))
        self._add_hooks_prerequisite(placements, design, result)
        parents = {child.key: parent for parent in design.walk() for child in parent.children}
        result.controls = {ou.key: [enabled for enabled in placements[ou.key].values()
                                    if not self._inherited(enabled, ou, parents, placements)]
                           for ou in design.walk() if ou.key in placements}
        return result

    def _governed(self, pack: ControlPack, design: LandingZoneDesign) -> list[OuNode]:
        """The selected OUs and every OU nested below them, once each, in tree order."""
        selected = {ou.key for name in pack.selectors for ou in self._selectors.get(name).select(design)}
        keys = selected | {nested.key for ou in design.walk() if ou.key in selected for nested in ou.descendants()}
        return [ou for ou in design.walk() if ou.key in keys]

    def _place(self, placements, ou: OuNode, control: CatalogControl, pack_id: str, parameters: dict) -> None:
        on_ou = placements.setdefault(ou.key, {})
        existing = on_ou.get(control.id)
        packs = (*existing.packs, pack_id) if existing else (pack_id,)
        on_ou[control.id] = EnabledControl(control, existing.parameters if existing else parameters, packs)

    def _parameters(self, design: LandingZoneDesign, pack: ControlPack, control: CatalogControl) -> dict:
        chosen = design.answers.pack_parameters.get(pack.id, {})
        defaults = {"AllowedRegions": design.answers.governed_regions}
        return {name: chosen.get(name, defaults.get(name)) for name in control.parameters
                if name in chosen or name in defaults}

    def _add_hooks_prerequisite(self, placements, design: LandingZoneDesign, result: ResolvedControls) -> None:
        proactive = [key for key, on_ou in placements.items() if any(e.control.is_proactive for e in on_ou.values())]
        if not proactive:
            return
        prerequisite = self._snapshot.proactive_prerequisite
        if prerequisite is None:
            result.warnings.append(UNRESOLVED_PREREQUISITE)
            return
        for ou in design.walk():
            if ou.key in proactive:
                self._place(placements, ou, prerequisite, HOOKS_PREREQUISITE_PACK, {})

    @staticmethod
    def _inherited(enabled: EnabledControl, ou: OuNode, parents: dict, placements: dict) -> bool:
        """A preventive control already enabled on an ancestor reaches this OU by inheritance."""
        if not enabled.control.is_preventive:
            return False
        ancestor = parents.get(ou.key)
        while ancestor is not None:
            if enabled.control.id in placements.get(ancestor.key, {}):
                return True
            ancestor = parents.get(ancestor.key)
        return False
