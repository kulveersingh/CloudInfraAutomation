import re
from typing import ClassVar

from app.providers.gcp.project.capabilities import GcpBlock
from app.providers.gcp.project.schema import GoogleProviderSchema, platform_managed
from app.synth.blocks.base import Block
from app.synth.request import ResourceSpec

TIER_2_CATEGORY = "Schema-driven (Tier 2)"
GOOGLE_TYPE_PATTERN = re.compile(r"^google_[a-z0-9_]+$")


class RawResourceBlock(GcpBlock):
    """Tier 2: any google_* resource type, with its arguments passed through from the request."""

    category = TIER_2_CATEGORY
    multi_region = "regional"
    terraform_type: ClassVar[str]

    @property
    def main_resource(self):
        return self.terraform_type, self.spec.id

    def contract_entry(self) -> dict:
        return {"terraformType": self.terraform_type}

    def emit(self, document) -> None:
        document.add_resource(self.terraform_type, self.spec.id, dict(self.spec.config.get("properties", {})))
        document.add_output(f"{self.spec.id}_id", {"value": f"${{{self.terraform_type}.{self.spec.id}.id}}"})


class RawResourceResolver:
    """A block class for any google_* type in the provider schema, except the ones the platform manages."""

    def __init__(self, schema: GoogleProviderSchema):
        self._schema = schema
        self._classes: dict[str, type[Block]] = {}

    def claims(self, type_name: str) -> bool:
        return bool(GOOGLE_TYPE_PATTERN.match(type_name))

    def supports(self, type_name: str) -> bool:
        return self.claims(type_name) and not platform_managed(type_name) and self._schema.has(type_name)

    def block_class(self, type_name: str) -> type[Block]:
        if type_name not in self._classes:
            self._classes[type_name] = type(f"Raw_{type_name}", (RawResourceBlock,), {
                "type_name": type_name, "display_name": type_name, "terraform_type": type_name})
        return self._classes[type_name]

    def problems_for(self, resource: ResourceSpec) -> list[str]:
        if platform_managed(resource.type):
            return [f"'{resource.type}' for '{resource.id}' is managed by the platform and cannot be requested."]
        if not self._schema.has(resource.type):
            return [f"Unknown resource type '{resource.type}' for '{resource.id}'."]
        subject = f"{resource.type} '{resource.id}'"
        extra = [f"{subject} accepts only 'properties' in config, not '{key}'."
                 for key in resource.config if key != "properties"]
        provided = resource.config.get("properties", {})
        if not isinstance(provided, dict):
            return [*extra, f"{subject} properties must be a JSON object."]
        return extra + [f"{subject} needs property '{name}'."
                        for name in self._schema.required(resource.type) if name not in provided]
