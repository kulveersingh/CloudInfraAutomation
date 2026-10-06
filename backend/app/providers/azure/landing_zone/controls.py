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


@cache
def azure_effects() -> dict[str, str]:
    """The effect each control is assigned with: Deny or DenyAction when preventive, an audit when detective."""
    document = yaml.safe_load((CATALOG_DIRECTORY / "controls.yaml").read_text())
    return {control_id: body["effect"] for control_id, body in document["controls"].items()}
