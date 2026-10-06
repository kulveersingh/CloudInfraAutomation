import json

from app.landing_zone.catalog.packs import PackRegistry
from app.landing_zone.catalog.resolver import PackResolver
from app.landing_zone.design import LandingZoneDesign, OrgCatalog
from app.landing_zone.diagram import OuDiagramRenderer
from app.landing_zone.document import design_document
from app.landing_zone.toolkit import LandingZoneRenderer
from app.providers.azure.landing_zone.answers import root_detail
from app.providers.azure.landing_zone.controls import azure_controls, azure_effects

REPOSITORY_NAME = "landing-zone-azure-infra"


class AzureLandingZoneBundle(LandingZoneRenderer):
    """`landing-zone-azure-infra`: the design, its diagrams and the controls per management group. The deployment
    stacks, seed script and workflow come with MC-5b (§22.12.5)."""

    def render(self, design: LandingZoneDesign, catalog: OrgCatalog) -> dict[str, str]:
        renderer = OuDiagramRenderer(root_detail(design.answers))
        return {"design.json": json.dumps(design_document(design), indent=2) + "\n",
                "docs/ou-structure.svg": renderer.svg(design), "docs/ou-structure.mmd": renderer.mermaid(design),
                "docs/controls.md": self._controls(design)}

    def _controls(self, design: LandingZoneDesign) -> str:
        controls = PackResolver(PackRegistry.default(), azure_controls()).resolve(design).controls
        effects = azure_effects()
        lines = [f"# Azure controls: {design.answers.organization_name}", "",
                 ("Azure Policy definitions are assigned on the top-most management group they apply to and govern "
                  "every management group, subscription and resource below it."), ""]
        for ou in design.walk():
            enabled = controls.get(ou.key, [])
            if enabled:
                lines += [f"## {ou.name} management group", "", "| Definition | Name | Behavior | Effect | Packs |",
                          "|---|---|---|---|---|",
                          *[f"| `{item.control.id}` | {item.control.name} | {item.control.behavior} | "
                            f"{effects[item.control.id]} | {', '.join(item.packs)} |" for item in enabled], ""]
        return "\n".join(lines)
