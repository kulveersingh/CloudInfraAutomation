import json

from app.landing_zone.design import LandingZoneDesign, OrgCatalog
from app.landing_zone.diagram import OuDiagramRenderer
from app.landing_zone.document import design_document
from app.landing_zone.toolkit import LandingZoneRenderer
from app.providers.gcp.landing_zone.answers import root_detail
from app.providers.gcp.landing_zone.deployments.base import DeploymentContext
from app.providers.gcp.landing_zone.deployments.foundation import FoundationDeployment
from app.providers.gcp.landing_zone.deployments.network import NetworkDeployment
from app.providers.gcp.landing_zone.deployments.projects import ProjectsDeployment
from app.providers.gcp.landing_zone.deployments.security import SecurityDeployment
from app.providers.gcp.landing_zone.deployments.structure import StructureDeployment
from app.providers.gcp.landing_zone.deployments.vault import VaultDeployment
from app.providers.gcp.landing_zone.seed import seed_project, seed_script

REPOSITORY_NAME = "landing-zone-gcp-infra"
INPUTS_FILE = "config/landing-zone.tfvars"
DEPLOYMENTS = [FoundationDeployment(), StructureDeployment(), ProjectsDeployment(), NetworkDeployment(),
               SecurityDeployment(), VaultDeployment()]


def as_json(document: dict) -> str:
    return json.dumps(document, indent=2) + "\n"


class GcpLandingZoneBundle(LandingZoneRenderer):
    """`landing-zone-gcp-infra` (§22.10.5): one directory per Infrastructure Manager deployment, applied in order
    from the seed project; the inputs, the seed script, the workflow, the design and its documents."""

    def render(self, design: LandingZoneDesign, catalog: OrgCatalog) -> dict[str, str]:
        context = DeploymentContext(design, catalog)
        renderer = OuDiagramRenderer(root_detail(design.answers))
        files = {"design.json": as_json(design_document(design)),
                 "docs/ou-structure.svg": renderer.svg(design), "docs/ou-structure.mmd": renderer.mermaid(design),
                 "docs/controls.md": self._controls(context), INPUTS_FILE: self._inputs(context),
                 "scripts/bootstrap-seed.sh": seed_script(design.answers.organization_name, context.answers),
                 ".github/workflows/apply.yml": self._workflow(design), "README.md": self._readme(design)}
        for deployment in DEPLOYMENTS:
            document = deployment.render(context)
            main = {section: body for section, body in document.items() if section != "variable"}
            files[f"deployments/{deployment.name}/main.tf.json"] = as_json(main)
            files[f"deployments/{deployment.name}/variables.tf.json"] = as_json({"variable": document["variable"]})
        return files

    def _inputs(self, context: DeploymentContext) -> str:
        values = {"organization_id": context.answers.organization_id, "billing_account": context.answers.billing_account,
                  "seed_project": seed_project(context.design.answers.organization_name),
                  "region": context.design.answers.home_region}
        return "".join(f"{name} = {json.dumps(value)}\n" for name, value in values.items())

    def _controls(self, context: DeploymentContext) -> str:
        lines = [f"# Google Cloud controls: {context.design.answers.organization_name}", "",
                 ("Org Policy constraints, IAM deny policies and Security Command Center detectors are set on the "
                  "top-most folder they apply to and govern every folder and project below it."), ""]
        for ou in context.design.walk():
            enabled = context.controls.get(ou.key, [])
            if enabled:
                lines += [f"## {ou.name} folder", "", "| Control | Name | Behavior | Implementation | Packs |",
                          "|---|---|---|---|---|",
                          *[f"| `{item.control.id}` | {item.control.name} | {item.control.behavior} | "
                            f"{item.control.implementation} | {', '.join(item.packs)} |" for item in enabled], ""]
        return "\n".join(lines)

    def _workflow(self, design: LandingZoneDesign) -> str:
        seed, region = seed_project(design.answers.organization_name), design.answers.home_region
        steps = "".join(f"""      - name: Validate {deployment.name}
        working-directory: deployments/{deployment.name}
        run: terraform init -backend=false -input=false && terraform validate
""" for deployment in DEPLOYMENTS)
        steps += "".join(f"""      - name: Apply {deployment.name}
        run: |
          DEPLOYMENT="projects/{seed}/locations/{region}/deployments/{deployment.name}"
          gcloud infra-manager previews create "projects/{seed}/locations/{region}/previews/${{{{ github.run_id }}}}-{deployment.name}" \\
            --deployment="$DEPLOYMENT" --local-source=deployments/{deployment.name} \\
            --inputs-file=config/landing-zone.tfvars --service-account="projects/{seed}/serviceAccounts/${{{{ vars.LZ_SERVICE_ACCOUNT }}}}"
          gcloud infra-manager deployments apply "$DEPLOYMENT" --local-source=deployments/{deployment.name} \\
            --inputs-file=config/landing-zone.tfvars --service-account="projects/{seed}/serviceAccounts/${{{{ vars.LZ_SERVICE_ACCOUNT }}}}"
""" for deployment in DEPLOYMENTS)
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
    environment: landing-zone
    steps:
      - uses: actions/checkout@v4
      - uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: 1.5.7
      - uses: google-github-actions/auth@v2
        with:
          workload_identity_provider: ${{{{ vars.LZ_WORKLOAD_IDENTITY_PROVIDER }}}}
          service_account: ${{{{ vars.LZ_SERVICE_ACCOUNT }}}}
      - uses: google-github-actions/setup-gcloud@v2
{steps}"""

    def _readme(self, design: LandingZoneDesign) -> str:
        answers = design.answers
        lines = [f"# {answers.organization_name} landing zone (Google Cloud)", "",
                 "Generated by the CloudInfra platform from the approved landing zone design. Change it through the",
                 "platform's Landing zone workflow; every change is planned, approved by a second admin and committed here.",
                 "", "![Folder structure](docs/ou-structure.svg)", "", "## Before the first apply", "",
                 "An organization admin runs `scripts/bootstrap-seed.sh <owner>/<repository>` once: it creates the seed",
                 "project, the Infrastructure Manager service account and Workload Identity Federation for this",
                 "repository, and prints the GitHub variables to set.", "",
                 "## Deployments (applied in this order by `.github/workflows/apply.yml`)", ""]
        lines += [f"{index}. `deployments/{deployment.name}`: {deployment.description}"
                  for index, deployment in enumerate(DEPLOYMENTS, start=1)]
        lines += ["", "## Left to a person", "",
                  "- VPC Service Controls perimeters start in dry-run: enforce each one once its dry-run shows no violations.",
                  "- Declared flows: set each `flow_N_service_attachment` input once the destination publishes its service."]
        if "backup" not in answers.infrastructure:
            lines.append("- Teardown backups: this design has no vault project, so set gcp_backup_project to one.")
        if answers.network.on_premises == "vpn":
            lines.append("- HA VPN: add the tunnels and BGP peers to `hub-vpn` with the on-premises side's details.")
        if answers.network.on_premises == "dedicated":
            lines.append("- Cloud Interconnect: order the connection, then attach it to the hub as a hybrid spoke.")
        return "\n".join([*lines, ""])
