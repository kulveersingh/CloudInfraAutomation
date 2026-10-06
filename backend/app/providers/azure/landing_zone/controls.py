from dataclasses import dataclass, field
from functools import cache
from pathlib import Path

import yaml

from app.landing_zone.catalog.controls import ControlCatalogSnapshot
from app.landing_zone.catalog.mappings import AllInherited, PackMappings, ProviderControls
from app.landing_zone.catalog.packs import PackRegistry

CATALOG_DIRECTORY = Path(__file__).with_name("catalog")


@cache
def azure_controls() -> ProviderControls:
    """Azure Policy definitions. An assignment on a management group governs everything below it, whatever its
    effect, so every control goes on the top-most targeted management group (L3)."""
    snapshot = ControlCatalogSnapshot.load(CATALOG_DIRECTORY / "controls.yaml")
    mappings = PackMappings.load(CATALOG_DIRECTORY / "mappings", snapshot, PackRegistry.default())
    return ProviderControls(snapshot, mappings, AllInherited())


@dataclass(frozen=True)
class AzureAssignment:
    """How a control is assigned: its effect, whether the definition takes it as a parameter, the values every
    assignment gets, and the definition's names for the pack's parameters."""

    effect: str
    effect_parameter: bool = True
    fixed_parameters: dict = field(default_factory=dict)
    parameter_names: dict = field(default_factory=dict)

    def parameters(self, pack_parameters: dict) -> dict:
        values = {**({"effect": self.effect} if self.effect_parameter else {}), **self.fixed_parameters,
                  **{self.parameter_names.get(name, name): value for name, value in pack_parameters.items()}}
        return {name: {"value": value} for name, value in values.items()}


@cache
def azure_assignments() -> dict[str, AzureAssignment]:
    document = yaml.safe_load((CATALOG_DIRECTORY / "controls.yaml").read_text())
    return {control_id: AzureAssignment(body["effect"], body.get("effect_parameter", True),
                                        body.get("fixed_parameters", {}), body.get("parameter_names", {}))
            for control_id, body in document["controls"].items()}


def azure_effects() -> dict[str, str]:
    """The effect each control is assigned with: Deny or DenyAction when preventive, an audit when detective."""
    return {control_id: assignment.effect for control_id, assignment in azure_assignments().items()}
