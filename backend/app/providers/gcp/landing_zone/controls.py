from functools import cache
from pathlib import Path

from app.landing_zone.catalog.controls import ControlCatalogSnapshot
from app.landing_zone.catalog.mappings import AllInherited, PackMappings, ProviderControls
from app.landing_zone.catalog.packs import PackRegistry

CATALOG_DIRECTORY = Path(__file__).with_name("catalog")


@cache
def gcp_controls() -> ProviderControls:
    """Org Policy, IAM deny and Security Command Center detectors. Policies and postures set on a folder govern
    everything below it, so every control goes on the top-most targeted folder (G3, G6)."""
    snapshot = ControlCatalogSnapshot.load(CATALOG_DIRECTORY / "controls.yaml")
    mappings = PackMappings.load(CATALOG_DIRECTORY / "mappings", snapshot, PackRegistry.default())
    return ProviderControls(snapshot, mappings, AllInherited())
