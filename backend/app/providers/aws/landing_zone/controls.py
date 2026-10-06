from functools import cache
from pathlib import Path

from app.landing_zone.catalog.controls import ControlCatalogSnapshot
from app.landing_zone.catalog.mappings import (
    ControlPrerequisite,
    PackMappings,
    PreventiveInherited,
    ProviderControls,
)
from app.landing_zone.catalog.packs import PackRegistry

CONTROL_ARN = "arn:aws:controlcatalog:::control/{}"
CATALOG_DIRECTORY = Path(__file__).with_name("catalog")
SNAPSHOT_PATH = CATALOG_DIRECTORY / "controls.yaml"
MAPPINGS_DIRECTORY = CATALOG_DIRECTORY / "mappings"
HOOKS_PREREQUISITE_PACK = "cloudformation-hooks"
UNRESOLVED_PREREQUISITE = ("Proactive controls need the CloudFormation-hooks prerequisite control (CT.CLOUDFORMATION.PR.1). "
                           "Refresh the control catalog to resolve its identifier.")


def control_identifier(control_id: str) -> str:
    """The global identifier Control Tower requires; regional AWS-GR_ identifiers are no longer supported."""
    return CONTROL_ARN.format(control_id)


@cache
def aws_snapshot() -> ControlCatalogSnapshot:
    """The Control Catalog snapshot: the Control Tower controls the AWS pack mappings use."""
    return ControlCatalogSnapshot.load(SNAPSHOT_PATH)


class HooksPrerequisite(ControlPrerequisite):
    """Proactive controls are CloudFormation hooks: the nodes that get one also need the hooks prerequisite."""

    def __init__(self, snapshot: ControlCatalogSnapshot):
        self._snapshot = snapshot

    def apply(self, placements, design, result):
        proactive = [key for key, on_ou in placements.by_node.items()
                     if any(enabled.control.is_proactive for enabled in on_ou.values())]
        if not proactive:
            return
        prerequisite = self._snapshot.proactive_prerequisite
        if prerequisite is None:
            result.warnings.append(UNRESOLVED_PREREQUISITE)
            return
        for ou in design.walk():
            if ou.key in proactive:
                placements.place(ou, prerequisite, HOOKS_PREREQUISITE_PACK, {})


@cache
def aws_controls(snapshot: ControlCatalogSnapshot | None = None) -> ProviderControls:
    """Control Tower's implementation of the packs: preventive controls flow down, the rest are per OU (F11)."""
    chosen = snapshot or aws_snapshot()
    mappings = PackMappings.load(MAPPINGS_DIRECTORY, chosen, PackRegistry.default())
    return ProviderControls(chosen, mappings, PreventiveInherited(), (HooksPrerequisite(chosen),))
