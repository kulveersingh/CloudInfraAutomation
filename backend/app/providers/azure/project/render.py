import json

from app.providers.azure.project.template import PARAMETERS_SCHEMA
from app.synth.render import FileRenderer, InfraJsonRenderer, ReadmeRenderer, RepositoryBundle
from app.synth.request import ProjectRequest

DATA_FILE = "main.json"
SHARED_FILE = "shared.json"
APP_FILE = "app.json"
SECONDARY_ACTIVATION = {"dr": "standby", "ha": "active"}


def as_json(document: dict) -> str:
    return json.dumps(document, indent=2) + "\n"


class TemplateFilesRenderer(FileRenderer):
    def render(self, request, template):
        return {DATA_FILE: as_json(template["data"]), SHARED_FILE: as_json(template["shared"]),
                APP_FILE: as_json(template["app"])}


class ParametersRenderer(FileRenderer):
    def render(self, request, template):
        return {f"parameters/{environment}.json": as_json({
            "$schema": PARAMETERS_SCHEMA, "contentVersion": "1.0.0.0",
            "parameters": {"projectName": {"value": request.project_name}, "environmentName": {"value": environment},
                           "resilienceMode": {"value": request.resilience.mode}}}) for environment in request.environments}


class AzureReadmeRenderer(FileRenderer):
    def __init__(self):
        self._readme = ReadmeRenderer(DATA_FILE)

    def render(self, request, template):
        readme = self._readme.render(request, template)["README.md"]
        note = ("`main.json` is the data stack: removing a service from it keeps the service, detached. "
                "`shared.json` is the shared stack (identities, access, wiring and queues) and `app.json` the app "
                "stack, one per region: removing a service from them deletes it. Run "
                "`az bicep decompile --file main.json` to read them as Bicep.\n")
        return {"README.md": readme + "\n" + note}


class StackWorkflowRenderer(FileRenderer):
    """Signs in with the deploy identity's federated credential, recovers the contract vault if a teardown left it
    soft-deleted, plans with what-if, then deploys the data stack, the shared stack and an app stack per region, in
    that order (§22.11.4). All values come from GitHub variables."""

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
    env:
      RG: ${{ vars.AZURE_RESOURCE_GROUP }}
      PARAMETERS: "@parameters/${{ vars.ENVIRONMENT_NAME }}.json"
    steps:
      - uses: actions/checkout@v4
      - uses: azure/login@v2
        with:
          client-id: ${{ vars.AZURE_CLIENT_ID }}
          tenant-id: ${{ vars.AZURE_TENANT_ID }}
          subscription-id: ${{ vars.AZURE_SUBSCRIPTION_ID }}
      - name: Deploy identity
        run: echo "PRINCIPAL=$(az identity list -g "$RG" --query "[?clientId=='${{ vars.AZURE_CLIENT_ID }}'].principalId" -o tsv)" >> "$GITHUB_ENV"
"""
    RECOVER_STEP = """      - name: Recover the contract vault after a teardown
        run: |
          az keyvault recover --name "${{ vars.CONTRACT_VAULT }}" --resource-group "$RG" --location "${{ vars.AZURE_PRIMARY_REGION }}" \\
            || echo "No soft-deleted contract vault to recover."
"""
    DATA_STEP = """      - name: Plan and deploy the data stack
        run: |
          az deployment group what-if --resource-group "$RG" --template-file main.json --parameters "$PARAMETERS" {inputs}
          az stack group create --name "{project}-data" --resource-group "$RG" --template-file main.json \\
            --parameters "$PARAMETERS" {inputs} \\
            --action-on-unmanage detachAll --deny-settings-mode denyWriteAndDelete \\
            --deny-settings-excluded-principals "$PRINCIPAL" --yes
"""
    SHARED_STEP = """      - name: Plan and deploy the shared stack
        run: |
          az deployment group what-if --resource-group "$RG" --template-file shared.json --parameters "$PARAMETERS" {inputs}
          az stack group create --name "{project}-shared" --resource-group "$RG" --template-file shared.json \\
            --parameters "$PARAMETERS" {inputs} \\
            --action-on-unmanage deleteResources --deny-settings-mode denyWriteAndDelete \\
            --deny-settings-excluded-principals "$PRINCIPAL" --yes
"""
    APP_STEP = """      - name: Plan and deploy the {label} app stack
        run: |
          az deployment group what-if --resource-group "$RG" --template-file app.json --parameters "$PARAMETERS" {inputs}
          az stack group create --name "{project}-${{{{ vars.{region} }}}}" --resource-group "$RG" --template-file app.json \\
            --parameters "$PARAMETERS" {inputs} \\
            --action-on-unmanage deleteResources --deny-settings-mode denyWriteAndDelete \\
            --deny-settings-excluded-principals "$PRINCIPAL" --yes
"""

    def render(self, request, template):
        networked = "subnetId" in template["app"]["parameters"]
        common = "costCenter=${{ vars.ORG_COST_CENTER }}"
        data = f"location=${{{{ vars.AZURE_PRIMARY_REGION }}}} {common}"
        data += " secondaryLocation=${{ vars.AZURE_SECONDARY_REGION }}" if request.resilience.is_multi_region else ""
        shared = f"location=${{{{ vars.AZURE_PRIMARY_REGION }}}} {common}"
        if "endpointSubnetId" in template["shared"]["parameters"]:
            shared += " endpointSubnetId=${{ vars.ENDPOINT_SUBNET_ID }}"
        steps = [self.RECOVER_STEP, self.DATA_STEP.format(project=request.project_name, inputs=data),
                 self.SHARED_STEP.format(project=request.project_name, inputs=shared),
                 self._app(request, "primary", "AZURE_PRIMARY_REGION", "active", "", networked, common)]
        activation = SECONDARY_ACTIVATION.get(request.resilience.mode)
        if activation:
            steps.append(self._app(request, "secondary", "AZURE_SECONDARY_REGION", activation, "_SECONDARY", networked,
                                   common))
        return {".github/workflows/deploy.yml": self.HEADER + "".join(steps)}

    def _app(self, request: ProjectRequest, role: str, region: str, activation: str, suffix: str, networked: bool,
             common: str) -> str:
        inputs = f"location=${{{{ vars.{region} }}}} {common} regionRole={role} activationState={activation}"
        inputs += f" subnetId=${{{{ vars.SUBNET_ID{suffix} }}}}" if networked else ""
        return self.APP_STEP.format(label=role, project=request.project_name, region=region, inputs=inputs)


def azure_bundle() -> RepositoryBundle:
    return RepositoryBundle([TemplateFilesRenderer(), InfraJsonRenderer(), ParametersRenderer(), StackWorkflowRenderer(),
                             AzureReadmeRenderer()])
