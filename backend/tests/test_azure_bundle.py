"""The Azure project repository (§22.11.4): templates, parameters, workflow and GitHub variables."""

import json

from app.adapters.ports import BootstrapOutputs
from app.providers.azure.provider import AzureProvider
from app.provisioning.topology import TopologyFactory
from app.synth.request import ProjectRequest, Resilience
from tests.azure_helpers import DR, azure_request, synthesize

SUBSCRIPTION = "0b1f6d5e-1234-4c3a-9a7b-2f6e8d9c0a11"


def files(payload: dict) -> dict[str, str]:
    request = ProjectRequest.model_validate(payload)
    return AzureProvider().project().bundle.render(request, synthesize(payload))


def test_repository_files():
    assert set(files(azure_request())) == {"main.json", "shared.json", "app.json", "parameters/dev.json",
                                           "parameters/test.json", "parameters/stage.json", "parameters/prod.json",
                                           "infra.json", "README.md",
                                           ".github/workflows/deploy.yml"}


def test_main_is_the_data_stack_shared_the_shared_stack_and_app_the_app_stack():
    rendered, document = files(azure_request()), synthesize(azure_request())
    assert (json.loads(rendered["main.json"]), json.loads(rendered["shared.json"]), json.loads(rendered["app.json"])) == (
        document["data"], document["shared"], document["app"])


def test_parameters_per_environment():
    parameters = json.loads(files(azure_request())["parameters/dev.json"])
    assert parameters["parameters"] == {"projectName": {"value": "invoice-ingest"}, "environmentName": {"value": "dev"},
                                        "resilienceMode": {"value": "single"}}


def test_readme_points_at_the_templates_and_bicep():
    readme = files(azure_request())["README.md"]
    assert ("regenerates `main.json` from `infra.json`" in readme, "az bicep decompile" in readme,
            "`shared.json` is the shared stack" in readme) == (True, True, True)


def test_workflow_signs_in_with_oidc_and_deploys_the_stacks():
    workflow = files(azure_request())[".github/workflows/deploy.yml"]
    assert ("azure/login@v2" in workflow, "client-id: ${{ vars.AZURE_CLIENT_ID }}" in workflow,
            "az deployment group what-if" in workflow,
            'az stack group create --name "invoice-ingest-data"' in workflow, "--action-on-unmanage detachAll" in workflow,
            "--action-on-unmanage deleteResources" in workflow, "--deny-settings-mode denyWriteAndDelete" in workflow,
            "costCenter=${{ vars.ORG_COST_CENTER }}" in workflow) == (True, True, True, True, True, True, True, True)


def test_single_region_projects_deploy_one_app_stack():
    workflow = files(azure_request())[".github/workflows/deploy.yml"]
    assert (workflow.count("az stack group create"), "regionRole=primary activationState=active" in workflow) == (3, True)


def test_dr_deploys_a_standby_app_stack_in_the_secondary_region():
    workflow = files(azure_request(resilience=DR))[".github/workflows/deploy.yml"]
    assert (workflow.count("az stack group create"), "regionRole=secondary activationState=standby" in workflow,
            "secondaryLocation=${{ vars.AZURE_SECONDARY_REGION }}" in workflow) == (4, True, True)


def test_attached_compute_passes_the_subnets():
    workflow = files(azure_request(attach=True))[".github/workflows/deploy.yml"]
    assert ("subnetId=${{ vars.SUBNET_ID }}" in workflow,
            "endpointSubnetId=${{ vars.ENDPOINT_SUBNET_ID }}" in workflow) == (True, True)


# ---- GitHub environment variables ----

class Context:
    def __init__(self, resilience: dict, networks: dict | None = None):
        self.topology = TopologyFactory.default().for_resilience(Resilience.model_validate(resilience))
        self.accounts = {"prod": SUBSCRIPTION}
        self.request = ProjectRequest.model_validate(azure_request(resilience=resilience))
        outputs = BootstrapOutputs(deployer_identity="/id", execution_identity="/id", federation="client-1",
                                   directory="tenant-1")
        self.bootstrap_outputs = {("prod", region): outputs for region in ("eastus2", "centralus")}
        self.networks = networks or {}


def variables(resilience: dict, networks: dict | None = None) -> dict:
    return AzureProvider().project().variables.for_environment(Context(resilience, networks), "prod")


def test_environment_variables_for_azure():
    assert variables({"mode": "single", "primary_region": "eastus2", "secondary_region": None}) == {
        "ENVIRONMENT_NAME": "prod", "AZURE_SUBSCRIPTION_ID": SUBSCRIPTION, "AZURE_CLIENT_ID": "client-1",
        "AZURE_TENANT_ID": "tenant-1", "AZURE_RESOURCE_GROUP": "rg-invoice-ingest-prod",
        "AZURE_PRIMARY_REGION": "eastus2"}


def test_secondary_region_variables():
    found = variables(DR)
    assert (found["AZURE_SECONDARY_REGION"], found["ACTIVATION_STATE_SECONDARY"]) == ("centralus", "standby")


def test_network_variables():
    vnet = f"/subscriptions/{SUBSCRIPTION}/resourceGroups/rg-network/providers/Microsoft.Network/virtualNetworks/v"
    network = {"network_ref": vnet, "subnet_refs": [f"{vnet}/subnets/functions", f"{vnet}/subnets/endpoints"],
               "firewall_refs": [], "cidr": "10.0.0.0/16"}
    found = variables({"mode": "single", "primary_region": "eastus2", "secondary_region": None},
                      {("prod", "eastus2"): network})
    assert (found["SUBNET_ID"], found["ENDPOINT_SUBNET_ID"]) == (f"{vnet}/subnets/functions", f"{vnet}/subnets/endpoints")
