import json

from app.landing_zone.catalog.packs import PackRegistry
from app.landing_zone.catalog.resolver import PackResolver
from app.landing_zone.design import LandingZoneDesign, OrgCatalog
from app.landing_zone.diagram import OuDiagramRenderer
from app.landing_zone.document import design_document
from app.landing_zone.toolkit import LandingZoneRenderer
from app.providers.gcp.landing_zone.answers import root_detail
from app.providers.gcp.landing_zone.controls import gcp_controls

REPOSITORY_NAME = "landing-zone-gcp-infra"


class GcpLandingZoneBundle(LandingZoneRenderer):
    """`landing-zone-gcp-infra`: the design, its diagrams and the controls per folder. The Infrastructure Manager
    deployments, seed script and workflow come with MC-3c (§22.10.5)."""

    def render(self, design: LandingZoneDesign, catalog: OrgCatalog) -> dict[str, str]:
        renderer = OuDiagramRenderer(root_detail(design.answers))
        return {"design.json": json.dumps(design_document(design), indent=2) + "\n",
                "docs/ou-structure.svg": renderer.svg(design), "docs/ou-structure.mmd": renderer.mermaid(design),
                "docs/controls.md": self._controls(design)}

    def _controls(self, design: LandingZoneDesign) -> str:
        controls = PackResolver(PackRegistry.default(), gcp_controls()).resolve(design).controls
        lines = [f"# Google Cloud controls: {design.answers.organization_name}", "",
                 ("Org Policy constraints, IAM deny policies and Security Command Center detectors are set on the "
                  "top-most folder they apply to and govern every folder and project below it."), ""]
        for ou in design.walk():
            enabled = controls.get(ou.key, [])
            if enabled:
                lines += [f"## {ou.name} folder", "", "| Control | Name | Behavior | Implementation | Packs |",
                          "|---|---|---|---|---|",
                          *[f"| `{item.control.id}` | {item.control.name} | {item.control.behavior} | "
                            f"{item.control.implementation} | {', '.join(item.packs)} |" for item in enabled], ""]
        return "\n".join(lines)
