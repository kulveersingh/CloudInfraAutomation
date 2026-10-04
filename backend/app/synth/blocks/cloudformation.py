import re
from functools import cached_property
from typing import ClassVar

from app.synth.blocks.base import Block
from app.synth.request import ResourceSpec
from app.synth.template import Template

SCHEMA_REGION = "us-east-1"
SEARCH_LIMIT = 50
TIER_2_CATEGORY = "Schema-driven (Tier 2)"
AWS_TYPE_PATTERN = re.compile(r"^AWS::[A-Za-z0-9]+::[A-Za-z0-9]+$")
PLATFORM_MANAGED_PREFIXES = ("AWS::IAM::", "AWS::Organizations::", "AWS::SSO::", "AWS::IdentityStore::",
                             "AWS::ControlTower::", "AWS::CloudFormation::")


class UnknownResourceTypeError(KeyError):
    pass


class CloudFormationSchemaCatalog:
    """Every CloudFormation resource type, from the official resource schemas bundled with cfn-lint."""

    def __init__(self, schema_manager, region: str):
        self._schema_manager = schema_manager
        self._region = region

    @classmethod
    def bundled(cls) -> "CloudFormationSchemaCatalog":
        from cfnlint.schema import PROVIDER_SCHEMA_MANAGER

        return cls(PROVIDER_SCHEMA_MANAGER, SCHEMA_REGION)

    @cached_property
    def _type_names(self) -> list[str]:
        return sorted(type_name for type_name in self._schema_manager.get_resource_types(self._region)
                      if AWS_TYPE_PATTERN.match(type_name))

    @cached_property
    def _type_set(self) -> frozenset[str]:
        return frozenset(self._type_names)

    def type_names(self) -> list[str]:
        return list(self._type_names)

    def has(self, type_name: str) -> bool:
        return type_name in self._type_set

    def required_properties(self, type_name: str) -> list[str]:
        if not self.has(type_name):
            raise UnknownResourceTypeError(type_name)
        schema = self._schema_manager.get_resource_schema(region=self._region, resource_type=type_name).schema
        return sorted(schema.get("required", []))

    def service(self, type_name: str) -> str:
        return type_name.split("::")[1]

    def search(self, text: str, limit: int = SEARCH_LIMIT) -> list[dict]:
        needle = text.lower()
        matches = [type_name for type_name in self._type_names if needle in type_name.lower()][:limit]
        return [{"type": type_name, "service": self.service(type_name), "required": self.required_properties(type_name)}
                for type_name in matches]


class SchemaDrivenBlock(Block):
    """Tier 2: any CloudFormation resource type, with properties passed through from the request."""

    category = TIER_2_CATEGORY
    multi_region = "regional"
    cloudformation_type: ClassVar[str]

    def contract_entry(self) -> dict:
        return {"cloudformationType": self.cloudformation_type}

    def emit(self, template: Template) -> None:
        resource = {"Type": self.cloudformation_type}
        properties = self.spec.config.get("properties", {})
        resource.update({"Properties": properties} if properties else {})
        template.add_resource(self.logical_id, resource)
        template.add_output(f"{self.logical_id}Ref", {"Value": {"Ref": self.logical_id}})


class SchemaDrivenBlockResolver:
    """Provides a block class for any AWS resource type in the schema catalog, except platform-managed ones."""

    def __init__(self, catalog: CloudFormationSchemaCatalog):
        self._catalog = catalog
        self._classes: dict[str, type[Block]] = {}

    def claims(self, type_name: str) -> bool:
        return bool(AWS_TYPE_PATTERN.match(type_name))

    def supports(self, type_name: str) -> bool:
        return self.claims(type_name) and not self._platform_managed(type_name) and self._catalog.has(type_name)

    def block_class(self, type_name: str) -> type[Block]:
        if type_name not in self._classes:
            self._classes[type_name] = self._new_block_class(type_name)
        return self._classes[type_name]

    def problems_for(self, resource: ResourceSpec) -> list[str]:
        if self._platform_managed(resource.type):
            return [f"'{resource.type}' for '{resource.id}' is managed by the platform and cannot be requested."]
        if not self._catalog.has(resource.type):
            return [f"Unknown resource type '{resource.type}' for '{resource.id}'."]
        provided = resource.config.get("properties", {})
        return [f"{resource.type} '{resource.id}' needs property '{name}'."
                for name in self._catalog.required_properties(resource.type) if name not in provided]

    def _platform_managed(self, type_name: str) -> bool:
        return type_name.startswith(PLATFORM_MANAGED_PREFIXES)

    def _new_block_class(self, type_name: str) -> type[Block]:
        _, service, resource = type_name.split("::")
        return type(f"{service}{resource}Block", (SchemaDrivenBlock,), {
            "type_name": type_name, "display_name": type_name, "cloudformation_type": type_name,
            "logical_id_suffix": resource})
