UNIQUE = "uniqueString(resourceGroup().id)"
CODE_NAME = f"[concat('stcode', {UNIQUE})]"
VAULT_NAME = f"[concat('kv', {UNIQUE})]"


def camel(resource_id: str) -> str:
    first, *rest = resource_id.split("-")
    return first + "".join(part.capitalize() for part in rest)


def variable(name: str) -> str:
    return f"[variables('{name}')]"


def bare(expression: str) -> str:
    """An expression without its brackets, to nest it in another one."""
    return expression[1:-1]


class AzureNaming:
    """Names of a service's Azure resources. Many are global, so they end with a hash of the resource group; each
    stays within its kind's length and alphabet."""

    def __init__(self, project_name: str, resource_id: str):
        self._project = project_name
        self.resource_id = resource_id
        self.variable = f"{camel(resource_id)}Name"

    def storage_account(self) -> str:  # 3-24 lowercase letters and digits
        return f"[concat('st', take('{self.resource_id.replace('-', '')}', 9), {UNIQUE})]"

    def cosmos_account(self) -> str:  # 3-44 lowercase letters, digits and hyphens
        return f"[concat('cosmos-', take('{self._project}-{self.resource_id}', 23), '-', {UNIQUE})]"

    def service_bus(self) -> str:  # 6-50 letters, digits and hyphens
        return f"[concat('sb-', take('{self._project}-{self.resource_id}', 33), '-', {UNIQUE})]"

    def function_app(self) -> str:  # 2-60; one per region
        return (f"[concat('func-', take('{self._project}-{self.resource_id}', 33), '-', "
                "uniqueString(resourceGroup().id, parameters('location')))]")

    def identity(self) -> str:
        return f"id-{self.resource_id}"

    def environment_variable(self, suffix: str) -> str:
        return f"{self.resource_id.upper().replace('-', '_')}_{suffix}"
