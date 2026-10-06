from typing import ClassVar

from app.providers.azure.project.capabilities import KEPT, LOCATION, AzureBlock
from app.providers.azure.project.schema import AzureResourceTypes, platform_managed
from app.synth.blocks.base import Block
from app.synth.request import ResourceSpec

TIER_2_CATEGORY = "Schema-driven (Tier 2)"


class RawResourceBlock(AzureBlock):
    """Tier 2: any Azure resource type at its latest stable API version, with its properties passed through. It
    lives in the data stack, so removing it keeps it (MC4-2)."""

    category = TIER_2_CATEGORY
    multi_region = "regional"
    retained_on_removal = True
    removal = KEPT
    arm_type: ClassVar[str]
    api_version: ClassVar[str]

    def contract_entry(self) -> dict:
        return {"armType": self.arm_type}

    def emit(self, documents) -> None:
        resource = {"type": self.arm_type, "apiVersion": self.api_version, "comments": self.spec.id,
                    "name": f"{self.request.project_name}-{self.spec.id}", "location": LOCATION}
        properties = self.spec.config.get("properties", {})
        documents.data.add_resource({**resource, **({"properties": properties} if properties else {})})


class RawResourceResolver:
    """A block class for any Azure resource type in the snapshot, except the ones the platform manages."""

    def __init__(self, types: AzureResourceTypes):
        self._types = types
        self._classes: dict[str, type[Block]] = {}

    def claims(self, type_name: str) -> bool:
        return type_name.startswith("Microsoft.") and "/" in type_name

    def supports(self, type_name: str) -> bool:
        return self.claims(type_name) and not platform_managed(type_name) and self._types.has(type_name)

    def block_class(self, type_name: str) -> type[Block]:
        if type_name not in self._classes:
            self._classes[type_name] = type(f"Raw_{type_name.replace('/', '_').replace('.', '_')}", (RawResourceBlock,), {
                "type_name": type_name, "display_name": type_name, "arm_type": type_name,
                "api_version": self._types.latest_stable(type_name)})
        return self._classes[type_name]

    def problems_for(self, resource: ResourceSpec) -> list[str]:
        if platform_managed(resource.type):
            return [f"'{resource.type}' for '{resource.id}' is managed by the platform and cannot be requested."]
        if not self._types.has(resource.type):
            return [f"Unknown resource type '{resource.type}' for '{resource.id}'."]
        subject = f"{resource.type} '{resource.id}'"
        extra = [f"{subject} accepts only 'properties' in config, not '{key}'."
                 for key in resource.config if key != "properties"]
        if not isinstance(resource.config.get("properties", {}), dict):
            return [*extra, f"{subject} properties must be a JSON object."]
        return extra
