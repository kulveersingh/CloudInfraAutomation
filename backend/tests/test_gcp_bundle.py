import json

from app.adapters.ports import BootstrapOutputs
from app.providers.gcp.provider import GcpProvider
from app.provisioning.topology import TopologyFactory
from app.synth.request import ProjectRequest, Resilience
from tests.gcp_helpers import DR, gcp_request, synthesize


def files(payload: dict) -> dict[str, str]:
    request = ProjectRequest.model_validate(payload)
    return GcpProvider().project().bundle.render(request, synthesize(payload))


def test_repository_files():
    assert set(files(gcp_request())) == {"main.tf.json", "variables.tf.json", "config/dev.tfvars", "config/test.tfvars",
                                         "config/stage.tfvars", "config/prod.tfvars", "infra.json", "README.md",
                                         ".github/workflows/deploy.yml"}


def test_variables_live_in_their_own_file():
    rendered = files(gcp_request())
    assert ("variable" in json.loads(rendered["variables.tf.json"]), "variable" in json.loads(rendered["main.tf.json"])) == (
        True, False)


def test_main_file_is_the_rest_of_the_document():
    document = synthesize(gcp_request())
    del document["variable"]
    assert json.loads(files(gcp_request())["main.tf.json"]) == document


def test_environment_inputs():
    assert files(gcp_request())["config/dev.tfvars"] == (
        'project_name = "invoice-ingest"\nenvironment_name = "dev"\nresilience_mode = "single"\n')


def test_readme_points_at_the_terraform_configuration():
    assert "regenerates `main.tf.json` from `infra.json`" in files(gcp_request())["README.md"]


def test_workflow_signs_in_with_workload_identity_and_applies_through_infrastructure_manager():
    workflow = files(gcp_request())[".github/workflows/deploy.yml"]
    assert ("google-github-actions/auth@v2" in workflow, "workload_identity_provider: ${{ vars.GCP_WORKLOAD_IDENTITY_PROVIDER }}" in workflow,
            "gcloud infra-manager previews create" in workflow, "gcloud infra-manager deployments apply" in workflow,
            "--inputs-file=config/${{ vars.ENVIRONMENT_NAME }}.tfvars" in workflow,
            "--service-account=${{ vars.IM_SERVICE_ACCOUNT }}" in workflow) == (True, True, True, True, True, True)


def test_workflow_deploys_the_primary_region_only_for_single_region_projects():
    workflow = files(gcp_request())[".github/workflows/deploy.yml"]
    assert (workflow.count("deployments apply"), "region_role=primary,activation_state=active" in workflow) == (1, True)


def test_dr_workflow_deploys_a_standby_secondary():
    workflow = files(gcp_request(resilience=DR))[".github/workflows/deploy.yml"]
    assert (workflow.count("deployments apply"), "region_role=secondary,activation_state=standby" in workflow) == (2, True)


def test_attached_compute_passes_the_network():
    workflow = files(gcp_request(attach=True))[".github/workflows/deploy.yml"]
    assert 'network=${{ vars.NETWORK }},subnetwork=${{ vars.SUBNETWORK }}' in workflow


# ---- GitHub environment variables ----

class Context:
    def __init__(self, resilience: dict, networks: dict | None = None):
        self.topology = TopologyFactory.default().for_resilience(Resilience.model_validate(resilience))
        self.accounts = {"prod": "cloudinfra-payments-prod"}
        outputs = BootstrapOutputs(deployer_identity="deploy@x", execution_identity="im@x", federation="projects/p/wif")
        self.bootstrap_outputs = {("prod", region): outputs for region in ("us-east1", "us-east4")}
        self.networks = networks or {}


def variables(resilience: dict, networks: dict | None = None) -> dict:
    return GcpProvider().project().variables.for_environment(Context(resilience, networks), "prod")


def test_environment_variables_for_google_cloud():
    found = variables({"mode": "single", "primary_region": "us-east1", "secondary_region": None})
    assert found == {"ENVIRONMENT_NAME": "prod", "GCP_PROJECT_ID": "cloudinfra-payments-prod", "GCP_PRIMARY_REGION": "us-east1",
                     "GCP_WORKLOAD_IDENTITY_PROVIDER": "projects/p/wif", "GCP_DEPLOY_SERVICE_ACCOUNT": "deploy@x",
                     "IM_SERVICE_ACCOUNT": "im@x", "CODE_BUCKET": "cloudinfra-artifacts-cloudinfra-payments-prod-us-east1"}


def test_secondary_region_variables():
    found = variables(DR)
    assert (found["GCP_SECONDARY_REGION"], found["ACTIVATION_STATE_SECONDARY"], found["CODE_BUCKET_SECONDARY"]) == (
        "us-east4", "standby", "cloudinfra-artifacts-cloudinfra-payments-prod-us-east4")


def test_network_variables():
    network = {"network_ref": "projects/h/global/networks/v", "subnet_refs": ["projects/h/regions/us-east1/subnetworks/s"],
               "firewall_refs": ["t1", "t2"], "cidr": "10.0.0.0/16"}
    found = variables({"mode": "single", "primary_region": "us-east1", "secondary_region": None},
                      {("prod", "us-east1"): network})
    assert (found["NETWORK"], found["SUBNETWORK"], found["NETWORK_TAGS"]) == (
        "projects/h/global/networks/v", "projects/h/regions/us-east1/subnetworks/s", '["t1","t2"]')
