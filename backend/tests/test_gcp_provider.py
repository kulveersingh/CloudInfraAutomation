import re

import pytest
from pydantic import ValidationError

from app.adapters.factory import AdapterFactory
from app.adapters.local_gcp import LocalGcp
from app.adapters.ports import BootstrapRequest
from app.errors import ValidationFailedError
from app.networks.models import NetworkInput
from app.providers.base import ProviderRegistry, Vocabulary
from app.providers.gcp.provider import GcpProvider
from app.seed import ReferenceData
from tests.factories import request_dict
from tests.lz_factories import answers_dict

ALEX = {"X-Actor": "alex", "X-Roles": "platform-admin"}
HOST = "cloudinfra-net-host"
NETWORK = {
    "provider": "gcp", "name": "Shared VPC", "account_id": "cloudinfra-payments-dev", "region": "us-east1",
    "network_ref": f"projects/{HOST}/global/networks/shared-vpc", "cidr": "10.40.0.0/16",
    "subnet_refs": [f"projects/{HOST}/regions/us-east1/subnetworks/payments-dev"],
    "firewall_refs": ["cloudinfra-payments-dev"],
}


def network(**overrides) -> NetworkInput:
    return NetworkInput.model_validate({**NETWORK, **overrides})


# ---- registration ----

def test_google_cloud_is_registered():
    assert [provider.id for provider in ProviderRegistry.default().all()] == ["aws", "gcp"]


def test_google_cloud_vocabulary():
    assert GcpProvider().vocabulary() == Vocabulary(
        cloud="Google Cloud", isolation_unit="project", hierarchy_node="folder", iac_document="Terraform configuration",
        deploy_unit="Infrastructure Manager deployment", preventive_policy="organization policy",
        private_network="Shared VPC", firewall_group="network tag", landing_zone_service="Google Cloud Setup",
        control_catalog="Security Command Center postures")


def test_google_cloud_default_regions():
    assert GcpProvider().default_regions() == ("us-east1", "us-east4")


def test_providers_api_lists_google_cloud(client):
    assert [provider["name"] for provider in client.get("/v1/providers").json()] == [
        "Amazon Web Services", "Google Cloud"]


# ---- registry data ----

def test_google_cloud_regions(client):
    regions = client.get("/v1/admin/regions", params={"provider": "gcp"}).json()
    assert ([region["id"] for region in regions if region["enabled"]][:3], len(regions)) == (
        ["europe-west1", "europe-west4", "us-central1"], 7)


def test_environments_are_bound_to_google_cloud_projects():
    bindings = {(binding.portfolio_id, binding.environment_id): binding.account_id
                for binding in ReferenceData().account_bindings() if binding.provider == "gcp"}
    assert (bindings[("pf-payments", "dev")], bindings[("pf-retail", "prod")]) == (
        "cloudinfra-payments-dev", "cloudinfra-retail-prod")


def test_google_cloud_networks_are_shared_vpc_subnets():
    [first, *_] = [item for item in ReferenceData().networks() if item.provider == "gcp"]
    assert (first.network_ref, first.subnet_refs, first.firewall_refs) == (
        f"projects/{HOST}/global/networks/shared-vpc",
        [f"projects/{HOST}/regions/us-east1/subnetworks/payments-sandbox"], ["cloudinfra-payments-sandbox"])


# ---- network checks ----

def test_valid_google_cloud_network_with_one_regional_subnet():
    assert network().subnet_refs == NETWORK["subnet_refs"]


@pytest.mark.parametrize(("field", "value", "message"), [
    ("account_id", "Payments", "Google Cloud project ids are 6 to 30 lowercase letters, digits and hyphens."),
    ("network_ref", "shared-vpc", "'shared-vpc' is not a VPC network (projects/…/global/networks/…)."),
    ("subnet_refs", [f"projects/{HOST}/regions/us-east4/subnetworks/x"],
     f"'projects/{HOST}/regions/us-east4/subnetworks/x' is not a subnetwork in us-east1 "
     "(projects/…/regions/us-east1/subnetworks/…)."),
    ("firewall_refs", ["Web"], "'Web' is not a network tag (lowercase letters, digits and hyphens)."),
])
def test_google_cloud_networks_explain_what_is_wrong(field, value, message):
    with pytest.raises(ValidationError, match=re.escape(message)):
        network(**{field: value})


# ---- local adapter ----

def test_factory_builds_the_local_google_cloud_adapter(settings):
    assert isinstance(AdapterFactory().clouds(settings).get("gcp"), LocalGcp)


def test_bootstrap_creates_workload_identity_service_accounts(tmp_path):
    outputs = LocalGcp(tmp_path).ensure_bootstrap_stack(BootstrapRequest(
        account_id="cloudinfra-payments-dev", region="us-east1", project="demo", repository="acme/demo-infra",
        environment="dev"))
    assert (outputs.deployer_identity, outputs.execution_identity) == (
        "cloudinfra-demo-deploy@cloudinfra-payments-dev.iam.gserviceaccount.com",
        "cloudinfra-demo-im@cloudinfra-payments-dev.iam.gserviceaccount.com")


def test_bootstrap_records_the_workload_identity_subject(tmp_path):
    adapter = LocalGcp(tmp_path)
    adapter.ensure_bootstrap_stack(BootstrapRequest(account_id="cloudinfra-payments-dev", region="us-east1",
                                                    project="demo", repository="acme/demo-infra", environment="dev"))
    assert adapter.stacks()[0]["trust_subject"] == "repo:acme/demo-infra:environment:dev"


def test_google_cloud_state_is_kept_apart_from_aws(tmp_path):
    LocalGcp(tmp_path).delete_stack("cloudinfra-payments-dev", "us-east1", "demo")
    assert (tmp_path / "gcp" / "stack-operations.json").exists() and not (tmp_path / "aws").exists()


# ---- what is not there yet ----

@pytest.mark.parametrize("part, message", [
    ("project", "Projects on Google Cloud are not available yet."),
    ("teardown", "Teardowns on Google Cloud are not available yet."),
    ("resources", "Releases on Google Cloud are not available yet."),
    ("landing_zone", "The Google Cloud landing zone is not available yet."),
])
def test_parts_still_to_come_say_so(part, message):
    with pytest.raises(ValidationFailedError, match=re.escape(message)):
        getattr(GcpProvider(), part)()


def test_google_cloud_project_preview_is_refused_clearly(client):
    response = client.post("/v1/projects:preview", json=request_dict(provider="gcp"))
    assert (response.status_code, response.json()["detail"]) == (422, "Projects on Google Cloud are not available yet.")


def test_google_cloud_landing_zone_is_refused_clearly(client):
    response = client.post("/v1/admin/landing-zone:propose",
                           json={"provider": "gcp", "answers": answers_dict(), "edits": []}, headers=ALEX)
    assert (response.status_code, response.json()["detail"]) == (
        422, "The Google Cloud landing zone is not available yet.")
