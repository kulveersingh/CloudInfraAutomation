"""Control packs: named sets of Control Tower controls with the OUs they target. One YAML file per pack."""

from dataclasses import dataclass
from functools import cache
from pathlib import Path

import yaml

from app.landing_zone.catalog.controls import CatalogError, ControlCatalogSnapshot
from app.landing_zone.catalog.selectors import SelectorRegistry

PACKS_DIRECTORY = Path(__file__).parent / "packs"
UNORDERED = 1000

# The controls profiles of §20.6, expressed as packs (§20.12.3).
PROFILE_PACKS = {
    "baseline": ["foundation"],
    "recommended": ["foundation", "data-protection", "network-hardening", "production-resilience"],
    "regulated": ["foundation", "data-protection", "network-hardening", "production-resilience", "logging-integrity",
                  "key-management"],
}


@dataclass(frozen=True)
class ControlPack:
    id: str
    version: int
    name: str
    description: str
    selectors: tuple[str, ...]
    control_ids: tuple[str, ...]
    optional: bool = False
    order: int = UNORDERED

    @classmethod
    def from_document(cls, document: dict) -> "ControlPack":
        return cls(id=document["id"], version=document["version"], name=document["name"],
                   description=document["description"], selectors=tuple(document["selectors"]),
                   control_ids=tuple(document["controls"]), optional=document.get("optional", False),
                   order=document.get("order", UNORDERED))


class PackRegistry:
    def __init__(self, packs: list[ControlPack], profiles: dict[str, list[str]]):
        self._packs = {pack.id: pack for pack in sorted(packs, key=lambda pack: (pack.order, pack.id))}
        self._profiles = profiles

    @classmethod
    def load(cls, directory: Path, snapshot: ControlCatalogSnapshot,
             profiles: dict[str, list[str]] = PROFILE_PACKS) -> "PackRegistry":
        packs = [ControlPack.from_document(yaml.safe_load(path.read_text())) for path in sorted(directory.glob("*.yaml"))]
        for pack in packs:
            cls._check(pack, snapshot)
        return cls(packs, profiles)

    @classmethod
    @cache
    def default(cls) -> "PackRegistry":
        return cls.load(PACKS_DIRECTORY, ControlCatalogSnapshot.default())

    def all(self) -> list[ControlPack]:
        return list(self._packs.values())

    def knows(self, pack_id: str) -> bool:
        return pack_id in self._packs

    def get(self, pack_id: str) -> ControlPack:
        if pack_id not in self._packs:
            raise CatalogError(f"Unknown control pack '{pack_id}'.")
        return self._packs[pack_id]

    def for_profile(self, profile: str) -> list[str]:
        return list(self._profiles[profile])

    @staticmethod
    def _check(pack: ControlPack, snapshot: ControlCatalogSnapshot) -> None:
        for control_id in pack.control_ids:
            if control_id not in snapshot.controls:
                raise CatalogError(f"Pack '{pack.id}' uses unknown control '{control_id}'.")
        for selector in pack.selectors:
            if not SelectorRegistry().knows(selector):
                raise CatalogError(f"Pack '{pack.id}' uses unknown selector '{selector}'.")
