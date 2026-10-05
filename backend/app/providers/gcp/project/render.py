import json

from app.synth.render import FileRenderer, InfraJsonRenderer, ReadmeRenderer, RepositoryBundle
from app.synth.request import ProjectRequest

MAIN_FILE = "main.tf.json"
VARIABLES_FILE = "variables.tf.json"
SECONDARY_ACTIVATION = {"dr": "standby", "ha": "active"}


def as_json(document: dict) -> str:
    return json.dumps(document, indent=2) + "\n"


class TerraformFilesRenderer(FileRenderer):
    """The configuration, with its variables in their own file as Terraform convention has it."""

    def render(self, request, template):
        main = {name: section for name, section in template.items() if name != "variable"}
        return {MAIN_FILE: as_json(main), VARIABLES_FILE: as_json({"variable": template["variable"]})}


class TfvarsRenderer(FileRenderer):
    def render(self, request, template):
        return {f"config/{environment}.tfvars": self._inputs(request, environment)
                for environment in request.environments}

    def _inputs(self, request: ProjectRequest, environment: str) -> str:
        inputs = {"project_name": request.project_name, "environment_name": environment,
                  "resilience_mode": request.resilience.mode}
        return "".join(f"{name} = {json.dumps(value)}\n" for name, value in inputs.items())


class InfraManagerWorkflowRenderer(FileRenderer):
    """Signs in with Workload Identity Federation, previews, then applies one Infrastructure Manager deployment per
    region. Identical in every repo apart from region steps; all values come from GitHub variables."""

    HEADER = """name: deploy
on:
  push:
    branches: [main]
  workflow_dispatch:
    inputs:
      environment:
        description: Environment to deploy
        required: true
        default: dev
permissions:
  id-token: write
  contents: read
concurrency:
  group: deploy-${{ inputs.environment || 'dev' }}
  cancel-in-progress: false
jobs:
  deploy:
    runs-on: ubuntu-latest
    environment: ${{ inputs.environment || 'dev' }}
    steps:
      - uses: actions/checkout@v4
      - uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: 1.5.7
      - name: Validate configuration
        run: terraform init -backend=false -input=false && terraform validate
      - uses: google-github-actions/auth@v2
        with:
          workload_identity_provider: ${{ vars.GCP_WORKLOAD_IDENTITY_PROVIDER }}
          service_account: ${{ vars.GCP_DEPLOY_SERVICE_ACCOUNT }}
      - uses: google-github-actions/setup-gcloud@v2
"""
    # Infrastructure Manager takes one inputs file, so each step adds its region's inputs to the environment's file.
    DEPLOY_STEP = """      - name: Deploy {label} region
        env:
          REGION: ${{{{ vars.{region_variable} }}}}
          DEPLOYMENT: projects/${{{{ vars.GCP_PROJECT_ID }}}}/locations/${{{{ vars.{region_variable} }}}}/deployments/cloudinfra-{project}-${{{{ vars.{region_variable} }}}}
          INPUTS: project_id=${{{{ vars.GCP_PROJECT_ID }}}},region=${{{{ vars.{region_variable} }}}},region_role={role},activation_state={activation},org_cost_center=${{{{ vars.ORG_COST_CENTER }}}}{extra}
        run: |
          git checkout -- config
          for pair in $(echo "$INPUTS" | tr ',' ' '); do echo "${{pair%%=*}} = \"${{pair#*=}}\"" >> "config/${{{{ vars.ENVIRONMENT_NAME }}}}.tfvars"; done
{tags}          gcloud infra-manager previews create "projects/${{{{ vars.GCP_PROJECT_ID }}}}/locations/$REGION/previews/${{{{ github.run_id }}}}-{label}" \\
            --deployment="$DEPLOYMENT" --local-source=. \\
            --inputs-file=config/${{{{ vars.ENVIRONMENT_NAME }}}}.tfvars --service-account=${{{{ vars.IM_SERVICE_ACCOUNT }}}}
          gcloud infra-manager deployments apply "$DEPLOYMENT" --local-source=. \\
            --inputs-file=config/${{{{ vars.ENVIRONMENT_NAME }}}}.tfvars --service-account=${{{{ vars.IM_SERVICE_ACCOUNT }}}}
"""
    CODE = ",code_bucket=${{{{ vars.CODE_BUCKET{suffix} }}}},code_object=bootstrap/{project}.zip"
    NETWORK = ",network=${{{{ vars.NETWORK{suffix} }}}},subnetwork=${{{{ vars.SUBNETWORK{suffix} }}}}"
    TAGS = """          echo 'network_tags = ${{{{ vars.NETWORK_TAGS{suffix} }}}}' >> "config/${{{{ vars.ENVIRONMENT_NAME }}}}.tfvars"
"""

    def render(self, request, template):
        variables = template.get("variable", {})
        steps = [self._step(request, variables, "primary", "GCP_PRIMARY_REGION", "primary", "active", "")]
        activation = SECONDARY_ACTIVATION.get(request.resilience.mode)
        if activation:
            steps.append(self._step(request, variables, "secondary", "GCP_SECONDARY_REGION", "secondary", activation,
                                    "_SECONDARY"))
        return {".github/workflows/deploy.yml": self.HEADER + "".join(steps)}

    def _step(self, request: ProjectRequest, variables: dict, label: str, region_variable: str, role: str,
              activation: str, suffix: str) -> str:
        project = request.project_name
        extra = self.CODE.format(suffix=suffix, project=project) if "code_bucket" in variables else ""
        networked = "network" in variables
        extra += self.NETWORK.format(suffix=suffix) if networked else ""
        tags = self.TAGS.format(suffix=suffix) if networked else ""
        return self.DEPLOY_STEP.format(label=label, region_variable=region_variable, role=role, activation=activation,
                                       extra=extra, tags=tags, project=project)


def gcp_bundle() -> RepositoryBundle:
    return RepositoryBundle([TerraformFilesRenderer(), InfraJsonRenderer(), TfvarsRenderer(),
                             InfraManagerWorkflowRenderer(), ReadmeRenderer(MAIN_FILE)])
