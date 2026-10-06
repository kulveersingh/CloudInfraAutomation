import json

from app.landing_zone.design import LandingZoneDesign, OrgCatalog
from app.landing_zone.diagram import OuDiagramRenderer
from app.landing_zone.document import design_document
from app.landing_zone.toolkit import LandingZoneRenderer
from app.providers.azure.landing_zone.answers import root_detail
from app.providers.azure.landing_zone.controls import azure_effects
from app.providers.azure.landing_zone.seed import ENVIRONMENT, seed_script
from app.providers.azure.landing_zone.stacks.base import PARAMETERS_SCHEMA, StackContext
from app.providers.azure.landing_zone.stacks.foundation import FoundationStack
from app.providers.azure.landing_zone.stacks.management import ManagementStack
from app.providers.azure.landing_zone.stacks.network import NetworkStack
from app.providers.azure.landing_zone.stacks.structure import StructureStack
from app.providers.azure.landing_zone.stacks.subscriptions import SubscriptionsStack
from app.providers.azure.landing_zone.stacks.vault import VaultStack

REPOSITORY_NAME = "landing-zone-azure-infra"
STACKS = [FoundationStack(), SubscriptionsStack(), StructureStack(), ManagementStack(), NetworkStack(), VaultStack()]
SUBSCRIPTION_IDS = "parameters/subscriptions.json"


def as_json(document: dict) -> str:
    return json.dumps(document, indent=2) + "\n"


class AzureLandingZoneBundle(LandingZoneRenderer):
    """`landing-zone-azure-infra` (§22.12.5): one directory per deployment stack, applied in order at the
    organization's management group; the seed script, the workflow, the design and its documents."""

    def render(self, design: LandingZoneDesign, catalog: OrgCatalog) -> dict[str, str]:
        context = StackContext(design, catalog)
        renderer = OuDiagramRenderer(root_detail(design.answers))
        files = {"design.json": as_json(design_document(design)),
                 "docs/ou-structure.svg": renderer.svg(design), "docs/ou-structure.mmd": renderer.mermaid(design),
                 "docs/controls.md": self._controls(context),
                 "scripts/bootstrap-seed.sh": seed_script(context.organization, context.answers),
                 ".github/workflows/apply.yml": self._workflow(context), "README.md": self._readme(context)}
        for stack in STACKS:
            files[f"stacks/{stack.name}/main.json"] = as_json(stack.render(context))
            files[f"stacks/{stack.name}/parameters.json"] = as_json(stack.parameters(context))
        return files

    def _controls(self, context: StackContext) -> str:
        effects = azure_effects()
        lines = [f"# Azure controls: {context.organization}", "",
                 ("Azure Policy definitions are assigned on the top-most management group they apply to and govern "
                  "every management group, subscription and resource below it. Policy Staging evaluates every control "
                  "without enforcing it."), ""]
        for ou in context.design.walk():
            enabled = context.controls.get(ou.key, [])
            if enabled:
                lines += [f"## {ou.name} management group", "", "| Definition | Name | Behavior | Effect | Packs |",
                          "|---|---|---|---|---|",
                          *[f"| `{item.control.id}` | {item.control.name} | {item.control.behavior} | "
                            f"{effects[item.control.id]} | {', '.join(item.packs)} |" for item in enabled], ""]
        return "\n".join(lines)

    def _workflow(self, context: StackContext) -> str:
        group, home = context.organization, context.home
        steps = ""
        for stack in STACKS:
            parameters = f"--parameters @stacks/{stack.name}/parameters.json" + (
                f" --parameters @{SUBSCRIPTION_IDS}" if stack.needs_subscription_ids else "")
            target = f'--management-group-id "{group}" --location "{home}" --template-file stacks/{stack.name}/main.json'
            steps += f"""      - name: Plan and apply {stack.name}
        run: |
          az deployment mg what-if {target} {parameters}
          az stack mg create --name "{stack.name}" {target} {parameters} \\
            --action-on-unmanage {stack.unmanaged} --deny-settings-mode denyWriteAndDelete \\
            --deny-settings-excluded-principals "$PRINCIPAL" --yes
"""
            if stack.name == SubscriptionsStack.name:
                steps += f"""      - name: Resolve the subscription ids
        run: |
          mkdir -p parameters
          az account alias list --query "value[].{{name: name, id: properties.subscriptionId}}" -o json \\
            | jq '{{"$schema": "{PARAMETERS_SCHEMA}", contentVersion: "1.0.0.0", parameters: {{subscriptionIds: {{value: (map({{(.name): .id}}) | add)}}}}}}' \\
            > {SUBSCRIPTION_IDS}
"""
        return f"""name: apply
on:
  push:
    branches: [main]
  workflow_dispatch:
permissions:
  id-token: write
  contents: read
concurrency:
  group: landing-zone
  cancel-in-progress: false
jobs:
  apply:
    runs-on: ubuntu-latest
    environment: {ENVIRONMENT}
    steps:
      - uses: actions/checkout@v4
      - uses: azure/login@v2
        with:
          client-id: ${{{{ vars.LZ_CLIENT_ID }}}}
          tenant-id: ${{{{ vars.LZ_TENANT_ID }}}}
          allow-no-subscriptions: true
      - name: Landing-zone identity
        run: echo "PRINCIPAL=$(az ad sp show --id "${{{{ vars.LZ_CLIENT_ID }}}}" --query id -o tsv)" >> "$GITHUB_ENV"
{steps}"""

    def _readme(self, context: StackContext) -> str:
        answers = context.design.answers
        lines = [f"# {context.organization} landing zone (Azure)", "",
                 "Generated by the CloudInfra platform from the approved landing zone design. Change it through the",
                 "platform's Landing zone workflow; every change is planned, approved by a second admin and committed here.",
                 "", "![Management group structure](docs/ou-structure.svg)", "", "## Before the first apply", "",
                 "A tenant admin runs `scripts/bootstrap-seed.sh <owner>/<repository>` once: it creates the",
                 f"`{context.organization}` management group and an app registration with a federated credential for",
                 "this repository, grants it Owner there and the billing role, and prints the GitHub variables to set.",
                 "", "## Stacks (applied in this order by `.github/workflows/apply.yml`)", ""]
        lines += [f"{index}. `stacks/{stack.name}`: {stack.description}" for index, stack in enumerate(STACKS, start=1)]
        lines += ["", "Subscriptions and the vault are detached, never deleted, when they leave the design.", "",
                  "## Left to a person", "",
                  "- Subscriptions detached from the design: move or cancel them.",
                  "- Gateway transit: once a hub gateway is up, allow it on the hub peerings and use it from the spokes."]
        if answers.network.on_premises == "vpn":
            lines.append("- VPN gateway: add the local network gateway and connection with the on-premises side's details.")
        if answers.network.on_premises == "dedicated":
            lines.append("- ExpressRoute: order the circuit, then connect it to each hub's ExpressRoute gateway.")
        return "\n".join([*lines, ""])
