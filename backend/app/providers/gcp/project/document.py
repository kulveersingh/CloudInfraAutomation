from app.synth.synthesizer import ENGINE_VERSION, GENERATOR_NAME

TERRAFORM = {"required_version": ">= 1.5.0, < 1.6.0",  # Infrastructure Manager runs Terraform up to 1.5.7
             "required_providers": {"google": {"source": "hashicorp/google", "version": ">= 7.21.0"}}}
PRIMARY_ONLY = "${local.is_primary ? 1 : 0}"
PROJECT_PROVIDER = {"project": "${var.project_id}", "region": "${var.region}", "default_labels": "${local.labels}"}


class DuplicateResourceError(ValueError):
    pass


def label(variable: str) -> str:
    """A label value from a variable: lowercase, with anything a label can't hold replaced."""
    return f'${{lower(replace(var.{variable}, "/[^a-zA-Z0-9_-]/", "-"))}}'


class TerraformDocument:
    """A Terraform configuration in JSON syntax, built section by section in a fixed order (deterministic)."""

    def __init__(self, provider: dict | None = None):
        """`provider`: the google provider's settings; a project's document by default (its project and region)."""
        self._provider = provider or PROJECT_PROVIDER
        self._variables: dict[str, dict] = {}
        self._locals: dict[str, object] = {}
        self._data: dict[str, dict[str, dict]] = {}
        self._resources: dict[str, dict[str, dict]] = {}
        self._outputs: dict[str, dict] = {}

    def add_variable(self, name: str, body: dict) -> None:
        self._variables.setdefault(name, body)

    def set_local(self, name: str, value) -> None:
        self._locals[name] = value

    def add_data(self, type_name: str, name: str, body: dict) -> None:
        self._data.setdefault(type_name, {}).setdefault(name, body)

    def add_resource(self, type_name: str, name: str, body: dict) -> None:
        resources = self._resources.setdefault(type_name, {})
        if name in resources:
            raise DuplicateResourceError(f"{type_name}.{name} is defined twice.")
        resources[name] = body

    def has_resource(self, type_name: str, name: str) -> bool:
        return name in self._resources.get(type_name, {})

    def add_output(self, name: str, body: dict) -> None:
        self._outputs[name] = body

    def to_dict(self) -> dict:
        sections = {"terraform": TERRAFORM, "variable": self._variables, "locals": self._locals,
                    "provider": {"google": self._provider},
                    "data": self._data, "resource": self._resources, "output": self._outputs}
        return {name: section for name, section in sections.items() if section}


def generator() -> dict:
    return {"name": GENERATOR_NAME, "version": ENGINE_VERSION}
