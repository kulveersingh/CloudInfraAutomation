from app.providers.azure.project.lint import (
    BroadRoleRule,
    LocalAuthRule,
    ResourceSchemaRule,
    StorageAccessRule,
)
from app.providers.azure.project.schema import AzureResourceTypes
from app.synth.lint import TemplateLinter

DEPLOYMENTS = "Microsoft.Resources/deployments"


def flatten(template: dict) -> list[dict]:
    """A stack's resources, including those inside its nested deployments."""
    found = []
    for resource in template["resources"]:
        found.append(resource)
        if resource["type"] == DEPLOYMENTS:
            found += flatten(resource["properties"]["template"])
    return found


class LandingZoneLinter:
    """MC-4b's rules on every resource of a stack. Role assignments above the resource group are the landing zone's
    job, so that project rule does not apply."""

    def __init__(self):
        self._linter = TemplateLinter([BroadRoleRule(), StorageAccessRule(), LocalAuthRule(),
                                       ResourceSchemaRule(AzureResourceTypes.bundled())])

    def lint(self, template: dict) -> list[str]:
        return self._linter.lint({"stack": {"resources": flatten(template)}})


def landing_zone_linter() -> LandingZoneLinter:
    return LandingZoneLinter()
