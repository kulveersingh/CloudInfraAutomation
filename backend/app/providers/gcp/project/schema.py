import gzip
import json
from functools import cache
from pathlib import Path

from app.synth.toolkit import SEARCH_LIMIT, ResourceTypeCatalog

BUNDLED_PATH = Path(__file__).with_name("google_provider_schema.json.gz")
PROVIDER_KEY = "registry.terraform.io/hashicorp/google"
# Types the platform manages itself; projects never request them (like IAM and Organizations on AWS).
PLATFORM_MANAGED_PREFIXES = ("google_project_iam", "google_organization", "google_folder", "google_service_account",
                             "google_billing", "google_iam_", "google_project_service")


def platform_managed(type_name: str) -> bool:
    return type_name.startswith(PLATFORM_MANAGED_PREFIXES) or "_iam_" in type_name


class GoogleProviderSchema(ResourceTypeCatalog):
    """Every google_* resource type with its arguments and nested blocks, from `terraform providers schema -json`,
    trimmed and committed so generation and the Tier-2 search work offline (§22.9.1)."""

    def __init__(self, resources: dict[str, dict], version: str):
        self._resources = resources
        self.version = version

    @classmethod
    @cache
    def bundled(cls) -> "GoogleProviderSchema":
        document = json.loads(gzip.decompress(BUNDLED_PATH.read_bytes()))
        return cls(document["resources"], document["version"])

    @classmethod
    def from_terraform(cls, output: dict, version: str) -> "GoogleProviderSchema":
        schemas = output["provider_schemas"][PROVIDER_KEY]["resource_schemas"]
        return cls({name: _trim(schema["block"]) for name, schema in sorted(schemas.items())}, version)

    def write(self, path: Path) -> None:
        document = {"provider": "hashicorp/google", "version": self.version, "resources": self._resources}
        path.write_bytes(gzip.compress(json.dumps(document, separators=(",", ":"), sort_keys=True).encode(), mtime=0))

    def has(self, type_name: str) -> bool:
        return type_name in self._resources

    def block(self, type_name: str) -> dict:
        return self._resources[type_name]

    def required(self, type_name: str) -> list[str]:
        return self._resources[type_name]["required"]

    def search(self, text: str, limit: int = SEARCH_LIMIT) -> list[dict]:
        needle = text.lower()
        matches = [name for name in self._resources if needle in name and not platform_managed(name)][:limit]
        return [{"type": name, "service": name.split("_")[1], "required": self.required(name)} for name in matches]


def _trim(block: dict) -> dict:
    attributes = block.get("attributes", {})
    trimmed = {"arguments": sorted(name for name, body in attributes.items()
                                   if body.get("required") or body.get("optional") or not body.get("computed")),
               "required": sorted(name for name, body in attributes.items() if body.get("required"))}
    nested = {name: {**_trim(body["block"]), "min_items": body.get("min_items", 0)}
              for name, body in block.get("block_types", {}).items()}
    return {**trimmed, "blocks": nested} if nested else trimmed
