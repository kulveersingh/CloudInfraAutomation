from app.synth.synthesizer import ENGINE_VERSION, GENERATOR_NAME

SCHEMA = "https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#"
PARAMETERS_SCHEMA = "https://schema.management.azure.com/schemas/2019-04-01/deploymentParameters.json#"
STRING = {"type": "string"}


class ArmTemplate:
    """An ARM JSON template under construction, in a fixed order (deterministic)."""

    def __init__(self):
        self._parameters: dict[str, dict] = {}
        self._variables: dict[str, object] = {}
        self._resources: list[dict] = []
        self._outputs: dict[str, dict] = {}

    def add_parameter(self, name: str, body: dict) -> None:
        self._parameters.setdefault(name, body)

    def set_variable(self, name: str, value) -> None:
        self._variables[name] = value

    def has_resource(self, comment: str, type_name: str | None = None) -> bool:
        return any(resource.get("comments") == comment and type_name in (None, resource["type"])
                   for resource in self._resources)

    def resources(self) -> list[dict]:
        return self._resources

    def add_resource(self, body: dict) -> None:
        self._resources.append(body)

    def add_output(self, name: str, body: dict) -> None:
        self._outputs[name] = body

    def to_dict(self) -> dict:
        document = {"$schema": SCHEMA, "contentVersion": "1.0.0.0",
                    "metadata": {"_generator": {"name": GENERATOR_NAME, "version": ENGINE_VERSION}},
                    "parameters": self._parameters, "variables": self._variables, "resources": self._resources}
        return {**document, **({"outputs": self._outputs} if self._outputs else {})}


class ArmDocuments:
    """A project's two stacks (MC4-2): `data` keeps what is removed from it, `app` (one per region) deletes it."""

    def __init__(self):
        self.data = ArmTemplate()
        self.app = ArmTemplate()

    def both(self) -> tuple[ArmTemplate, ArmTemplate]:
        return self.data, self.app

    def to_dict(self) -> dict:
        return {"data": self.data.to_dict(), "app": self.app.to_dict()}
