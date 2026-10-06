from abc import ABC, abstractmethod

from app.providers.azure.project.schema import AzureResourceTypes
from app.synth.lint import LintRule, TemplateLinter

ROLE = "Microsoft.Authorization/roleAssignments"
BROAD_ROLES = {"8e3af657-a8ff-443c-a75c-2fe8c4bcb635": "Owner", "b24988ac-6180-42a0-ab88-20f7382dd24c": "Contributor",
               "18d7d88d-d35e-4fb5-a5c3-7773c20a72d9": "User Access Administrator"}
LOCAL_AUTH_TYPES = ("Microsoft.DocumentDB/databaseAccounts", "Microsoft.ServiceBus/namespaces")
# Keywords of an ARM resource rather than properties of its type.
ARM_KEYWORDS = frozenset({"type", "apiVersion", "dependsOn", "condition", "scope", "comments", "copy"})


class ArmRule(LintRule, ABC):
    """A check on each resource of a project's two ARM templates."""

    def findings(self, template):
        return [finding for stack in template.values() for resource in stack["resources"]
                for finding in self.check(resource, f"{resource['type']} {resource.get('comments') or resource['name']}")]

    @abstractmethod
    def check(self, resource: dict, subject: str) -> list[str]:
        ...


class BroadRoleRule(ArmRule):
    def check(self, resource, subject):
        if resource["type"] != ROLE:
            return []
        definition = resource["properties"]["roleDefinitionId"]
        return [f"{subject}: broad role {name}." for role, name in BROAD_ROLES.items() if role in definition]


class RoleScopeRule(ArmRule):
    def check(self, resource, subject):
        scope = resource.get("scope", "")
        above = resource["type"] == ROLE and ("subscription()" in scope or "managementGroup" in scope)
        return [f"{subject}: role assignment above the resource group."] if above else []


class StorageAccessRule(ArmRule):
    def check(self, resource, subject):
        if resource["type"] != "Microsoft.Storage/storageAccounts":
            return []
        properties = resource.get("properties", {})
        return [*([f"{subject}: shared key access is on."] if properties.get("allowSharedKeyAccess") is not False else []),
                *([f"{subject}: public blob access is on."] if properties.get("allowBlobPublicAccess") is not False
                  else [])]


class LocalAuthRule(ArmRule):
    def check(self, resource, subject):
        local = resource["type"] in LOCAL_AUTH_TYPES and resource.get("properties", {}).get("disableLocalAuth") is not True
        return [f"{subject}: local authentication is on."] if local else []


class FunctionIdentityRule(ArmRule):
    def check(self, resource, subject):
        if resource["type"] != "Microsoft.Web/sites" or resource.get("identity", {}).get("type") == "UserAssigned":
            return []
        return [f"{subject}: function app has no identity of its own."]


class ResourceSchemaRule(ArmRule):
    """The type and API version exist; for pinned versions, every property is known and required ones are set."""

    def __init__(self, types: AzureResourceTypes):
        self._types = types

    def check(self, resource, subject):
        if not self._types.has(resource["type"]):
            return [f"{subject}: unknown resource type."]
        if resource["apiVersion"] not in self._types.versions(resource["type"]):
            return [f"{subject}: unknown API version {resource['apiVersion']}."]
        schema = self._types.schema(resource["type"], resource["apiVersion"])
        if schema is None:
            return []
        body = {key: value for key, value in resource.items() if key not in ARM_KEYWORDS}
        return [f"{subject}: {problem}" for problem in self._problems(schema, body, "")]

    def _problems(self, schema: dict, body: dict, path: str) -> list[str]:
        properties = schema["properties"]
        found = [f"unknown property '{path}{key}'." for key in body if key not in properties]
        found += [f"missing required property '{path}{key}'." for key in schema["required"] if key not in body]
        for key, value in body.items():
            nested = properties.get(key)
            for item in (value if isinstance(value, list) else [value]):
                if nested is not None and isinstance(item, dict):
                    found += self._problems(nested, item, f"{path}{key}.")
        return found


def azure_linter() -> TemplateLinter:
    return TemplateLinter([BroadRoleRule(), RoleScopeRule(), StorageAccessRule(), LocalAuthRule(), FunctionIdentityRule(),
                           ResourceSchemaRule(AzureResourceTypes.bundled())])
