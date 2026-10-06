"""The Azure resource types snapshot (§22.11.2): every resource type with its API versions, from the Bicep type
index, and a trimmed property schema for the API versions the curated services pin."""

import gzip
import json
from functools import cache
from pathlib import Path

from app.synth.toolkit import SEARCH_LIMIT, ResourceTypeCatalog

BUNDLED_PATH = Path(__file__).with_name("azure_resource_types.json.gz")
REQUIRED, READ_ONLY = 1, 2
MAX_DEPTH = 6
# Types the platform manages itself; projects never request them (like IAM on AWS).
PLATFORM_MANAGED_PREFIXES = ("microsoft.authorization/", "microsoft.management/", "microsoft.resources/",
                             "microsoft.managedidentity/", "microsoft.network/virtualnetworks")


def platform_managed(type_name: str) -> bool:
    return type_name.lower().startswith(PLATFORM_MANAGED_PREFIXES)


def stable(versions: list[str]) -> list[str]:
    return [version for version in versions if "preview" not in version]


class AzureResourceTypes(ResourceTypeCatalog):
    """Resource types by lowercase name with their API versions, and the property schemas of the pinned versions.
    A schema node is {"required": [...], "properties": {name: node | None}}; None accepts any value."""

    def __init__(self, types: dict[str, list[str]], schemas: dict[str, dict], names: dict[str, str]):
        self._types = types
        self._schemas = schemas
        self._names = names

    @classmethod
    @cache
    def bundled(cls) -> "AzureResourceTypes":
        return cls.read(BUNDLED_PATH)

    @classmethod
    def read(cls, path: Path) -> "AzureResourceTypes":
        document = json.loads(gzip.decompress(path.read_bytes()))
        return cls(document["types"], document["schemas"], document["names"])

    def write(self, path: Path) -> None:
        document = {"types": self._types, "schemas": self._schemas, "names": self._names}
        path.write_bytes(gzip.compress(json.dumps(document, separators=(",", ":"), sort_keys=True).encode(), mtime=0))

    def has(self, type_name: str) -> bool:
        return type_name.lower() in self._types

    def versions(self, type_name: str) -> list[str]:
        return self._types.get(type_name.lower(), [])

    def latest_stable(self, type_name: str) -> str:
        versions = self.versions(type_name)
        return (stable(versions) or versions)[-1]

    def schema(self, type_name: str, version: str) -> dict | None:
        return self._schemas.get(f"{type_name.lower()}@{version}")

    def search(self, text: str, limit: int = SEARCH_LIMIT) -> list[dict]:
        needle = text.lower()
        matches = [name for name in self._types if needle in name and not platform_managed(name)][:limit]
        return [{"type": self._names[name], "service": self._names[name].split("/")[0].removeprefix("Microsoft."),
                 "required": ["name"]} for name in matches]


class BicepTypesReader:
    """Builds the snapshot from Azure/bicep-types-az: `index.json`, and each pinned version's `types.json`."""

    def __init__(self, fetch):
        self._fetch = fetch  # path relative to generated/ → parsed JSON

    def read(self, pinned: list[str]) -> AzureResourceTypes:
        index = self._fetch("index.json")["resources"]
        types: dict[str, list[str]] = {}
        names: dict[str, str] = {}
        for key in index:
            type_name, version = key.rsplit("@", 1)
            types.setdefault(type_name.lower(), []).append(version)
            names[type_name.lower()] = type_name
        schemas = {}
        for key in pinned:
            file, position = index[key]["$ref"].split("#/")
            nodes = self._fetch(file)
            schemas[key.lower()] = Trimmer(nodes).resource(nodes[int(position)])
        return AzureResourceTypes({name: sorted(versions) for name, versions in sorted(types.items())}, schemas, names)


class Trimmer:
    """Keeps what a template may set: writable properties, which are required, and their nested objects."""

    def __init__(self, nodes: list[dict]):
        self._nodes = nodes
        self._trimmed: dict[tuple[int, int], dict | None] = {}

    def resource(self, resource_type: dict) -> dict:
        return self._node(resource_type["body"], 0)

    def _resolve(self, reference: dict) -> dict:
        return self._nodes[self._position(reference)]

    @staticmethod
    def _position(reference: dict) -> int:
        return int(reference["$ref"].split("/")[-1])

    def _node(self, reference: dict, depth: int) -> dict | None:
        """Each node is trimmed once per depth: shared types are referenced from many places."""
        key = (self._position(reference), depth)
        if key not in self._trimmed:
            self._trimmed[key] = self._trim(self._resolve(reference), depth)
        return self._trimmed[key]

    def _trim(self, node: dict, depth: int) -> dict | None:
        kind = node["$type"]
        if depth >= MAX_DEPTH:
            return None
        if kind == "ArrayType":
            return self._node(node["itemType"], depth)
        if kind == "ObjectType":
            if "additionalProperties" in node and not node.get("properties"):
                return None
            return self._object(node.get("properties", {}), depth)
        if kind == "DiscriminatedObjectType":
            return self._variants(node, depth)
        return None

    def _variants(self, node: dict, depth: int) -> dict:
        """All variants' properties together; one the variants define differently accepts any value."""
        base = dict(node.get("baseProperties", {}))
        variants = [self._resolve(element).get("properties", {}) for element in node["elements"].values()]
        names = {name for variant in variants for name in variant}
        shared = {name for name in names if sum(name in variant for variant in variants) > 1}
        merged = self._object({**base, **{name: body for variant in variants for name, body in variant.items()
                                          if name not in shared}}, depth)
        merged["properties"].update({name: None for name in shared | {node["discriminator"]}})
        return merged

    def _object(self, properties: dict, depth: int) -> dict:
        writable = {name: body for name, body in properties.items() if not body.get("flags", 0) & READ_ONLY}
        return {"required": sorted(name for name, body in writable.items() if body.get("flags", 0) & REQUIRED),
                "properties": {name: self._node(body["type"], depth + 1) for name, body in sorted(writable.items())}}
