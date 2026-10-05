from abc import ABC, abstractmethod

from app.providers.gcp.project.schema import GoogleProviderSchema
from app.synth.lint import LintRule, TemplateLinter

PRIMITIVE_ROLES = frozenset({"roles/owner", "roles/editor", "roles/viewer"})
PUBLIC_MEMBERS = frozenset({"allUsers", "allAuthenticatedUsers"})
WORKLOAD_SUFFIX = "@${var.project_id}.iam.gserviceaccount.com"
# Project-level roles that exist only at project level and carry no data access.
PROJECT_ONLY_ROLES = frozenset({"roles/eventarc.eventReceiver"})
META_ARGUMENTS = frozenset({"count", "for_each", "depends_on", "lifecycle", "provider"})


class TerraformRule(LintRule, ABC):
    """A check on each resource of a Terraform JSON document."""

    def findings(self, template):
        return [finding for type_name, resources in template.get("resource", {}).items()
                for name, body in resources.items() for finding in self.check(type_name, name, body)]

    @abstractmethod
    def check(self, type_name: str, name: str, body: dict) -> list[str]:
        ...


class PrimitiveRoleRule(TerraformRule):
    def check(self, type_name, name, body):
        role = body.get("role") if type_name.endswith("_iam_member") else None
        return [f"{type_name}.{name}: primitive role '{role}'."] if role in PRIMITIVE_ROLES else []


class PublicMemberRule(TerraformRule):
    def check(self, type_name, name, body):
        member = body.get("member") if type_name.endswith("_iam_member") else None
        return [f"{type_name}.{name}: public member '{member}'."] if member in PUBLIC_MEMBERS else []


class PublicAccessPreventionRule(TerraformRule):
    def check(self, type_name, name, body):
        if type_name != "google_storage_bucket" or body.get("public_access_prevention") == "enforced":
            return []
        return [f"{type_name}.{name}: public access prevention is not enforced."]


class UnconditionedProjectRoleRule(TerraformRule):
    """A workload's project-level binding must be narrowed to its resource by an IAM condition."""

    def check(self, type_name, name, body):
        workload = type_name == "google_project_iam_member" and str(body.get("member", "")).endswith(WORKLOAD_SUFFIX)
        if not workload or "condition" in body or body.get("role") in PROJECT_ONLY_ROLES:
            return []
        return [f"{type_name}.{name}: project-wide role '{body.get('role')}' for a workload without a condition."]


class ProviderSchemaRule(TerraformRule):
    """Every argument and nested block exists in the google provider, and required arguments are present."""

    def __init__(self, schema: GoogleProviderSchema):
        self._schema = schema

    def check(self, type_name, name, body):
        if not self._schema.has(type_name):
            return [f"{type_name}.{name}: unknown resource type."]
        return [f"{type_name}.{name}: {problem}" for problem in self._problems(self._schema.block(type_name), body, "")]

    def _problems(self, block: dict, body: dict, path: str) -> list[str]:
        nested = block.get("blocks", {})
        unknown, inside = [], []
        for key, value in body.items():
            if key == "dynamic":
                inside += [problem for block_name, spec in value.items()
                           for problem in self._nested(nested, block_name, spec["content"], path)]
            elif key in nested:
                inside += self._nested(nested, key, value, path)
            elif key not in block["arguments"] and not (key in META_ARGUMENTS and not path):
                unknown.append(f"unknown argument '{path}{key}'.")
        missing = [f"missing required argument '{path}{key}'." for key in block["required"] if key not in body]
        return unknown + missing + inside

    def _nested(self, nested: dict, key: str, value, path: str) -> list[str]:
        if key not in nested:
            return [f"unknown argument '{path}{key}'."]
        items = value if isinstance(value, list) else [value]
        return [problem for item in items for problem in self._problems(nested[key], item, f"{path}{key}.")]


def gcp_linter() -> TemplateLinter:
    return TemplateLinter([PrimitiveRoleRule(), PublicMemberRule(), PublicAccessPreventionRule(),
                           UnconditionedProjectRoleRule(), ProviderSchemaRule(GoogleProviderSchema.bundled())])
