"""Azure registered as a provider (§22.11, MC-4a): vocabulary, regions and their pairs, subscription bindings,
VNet checks, the local adapter, and clear refusals for the parts still to come."""

import re
import uuid

import pytest
from pydantic import ValidationError

from app.adapters.factory import AdapterFactory
from app.adapters.ports import BackupSource, BootstrapRequest
from app.errors import ValidationFailedError
from app.networks.models import NetworkInput
from app.providers.base import ProviderRegistry, Vocabulary
from app.seed import ReferenceData
from tests.factories import request_dict

ALEX = {"X-Actor": "alex", "X-Roles": "platform-admin"}
SUBSCRIPTION = "0b1f6d5e-1234-4c3a-9a7b-2f6e8d9c0a11"
VNET = f"/subscriptions/{SUBSCRIPTION}/resourceGroups/rg-network/providers/Microsoft.Network/virtualNetworks/vnet-eastus2"
NSG = f"/subscriptions/{SUBSCRIPTION}/resourceGroups/rg-network/providers/Microsoft.Network/networkSecurityGroups/nsg-apps"
NETWORK = {"provider": "azure", "name": "Spoke VNet", "account_id": SUBSCRIPTION, "region": "eastus2", "network_ref": VNET,
           "cidr": "10.192.0.0/16", "subnet_refs": [f"{VNET}/subnets/functions", f"{VNET}/subnets/endpoints"],
           "firewall_refs": [NSG]}


def provider():
    from app.providers.azure.provider import AzureProvider

    return AzureProvider()


def network(**overrides) -> NetworkInput:
    return NetworkInput.model_validate({**NETWORK, **overrides})


def local_azure(root):
    from app.adapters.local_azure import LocalAzure

    return LocalAzure(root)


# ---- registration ----

def test_azure_is_registered_third():
    assert [item.id for item in ProviderRegistry.default().all()] == ["aws", "gcp", "azure"]


def test_azure_vocabulary():
    assert provider().vocabulary() == Vocabulary(
        cloud="Azure", isolation_unit="subscription", hierarchy_node="management group", iac_document="ARM template",
        deploy_unit="deployment stack", preventive_policy="Azure Policy", private_network="VNet",
        firewall_group="network security group", landing_zone_service="Azure Landing Zones",
        control_catalog="Azure Policy initiatives")


def test_azure_starts_on_a_region_pair():
    primary, secondary = provider().default_regions()
    assert ((primary, secondary), provider().region_pair(primary)) == (("eastus2", "centralus"), "centralus")


@pytest.mark.parametrize("region, pair", [("eastus", "westus"), ("westus", "eastus"), ("northeurope", "westeurope"),
                                          ("swedencentral", "swedensouth"), ("qatarcentral", None)])
def test_region_pairs(region, pair):
    assert provider().region_pair(region) == pair


def test_providers_api_lists_azure(client):
    clouds = client.get("/v1/providers").json()
    assert ([item["name"] for item in clouds], clouds[2]["document_file"]) == (
        ["Amazon Web Services", "Google Cloud", "Azure"], "main.json")


# ---- registry data ----

def test_azure_regions(client):
    regions = client.get("/v1/admin/regions", params={"provider": "azure"}).json()
    assert ([region["id"] for region in regions if region["enabled"]][:3], len(regions)) == (
        ["centralus", "eastus", "eastus2"], 7)


def test_environments_are_bound_to_azure_subscriptions():
    bindings = {(binding.portfolio_id, binding.environment_id): binding.account_id
                for binding in ReferenceData().account_bindings() if binding.provider == "azure"}
    assert (len(bindings), bindings[("pf-payments", "dev")]) == (
        15, str(uuid.uuid5(uuid.NAMESPACE_URL, "cloudinfra:azure:pf-payments:dev")))


def test_azure_networks_are_spoke_vnets_with_a_function_subnet():
    [first, *_] = [item for item in ReferenceData().networks() if item.provider == "azure"]
    assert (re.fullmatch(r"/subscriptions/[0-9a-f-]{36}/resourceGroups/rg-network/providers/Microsoft.Network/"
                         r"virtualNetworks/vnet-eastus2", first.network_ref) is not None,
            first.subnet_refs[0].endswith("/subnets/functions"), first.region) == (True, True, "eastus2")


# ---- network checks ----

def test_a_valid_azure_network():
    assert network().subnet_refs[0].endswith("/subnets/functions")


@pytest.mark.parametrize(("field", "value", "message"), [
    ("account_id", "payments-dev", "Azure subscription ids are GUIDs."),
    ("network_ref", "vnet-eastus2",
     "'vnet-eastus2' is not a VNet (/subscriptions/…/resourceGroups/…/providers/Microsoft.Network/virtualNetworks/…)."),
    ("subnet_refs", [f"{VNET}-other/subnets/functions"], f"'{VNET}-other/subnets/functions' is not a subnet of {VNET}."),
    ("firewall_refs", ["nsg-apps"], "'nsg-apps' is not a network security group "
                                    "(/subscriptions/…/providers/Microsoft.Network/networkSecurityGroups/…)."),
])
def test_azure_networks_explain_what_is_wrong(field, value, message):
    with pytest.raises(ValidationError, match=re.escape(message)):
        network(**{field: value})


def test_azure_networks_can_be_registered(client):
    response = client.post("/v1/admin/networks", json={**NETWORK, "is_default": False})
    assert (response.status_code, response.json()["provider"]) == (201, "azure")


# ---- local adapter ----

def bootstrap_request() -> BootstrapRequest:
    return BootstrapRequest(account_id=SUBSCRIPTION, region="eastus2", project="demo", repository="acme/demo-infra",
                            environment="dev")


def test_factory_builds_the_local_azure_adapter(settings):
    from app.adapters.local_azure import LocalAzure

    assert isinstance(AdapterFactory().clouds(settings).get("azure"), LocalAzure)


def test_bootstrap_creates_a_federated_deploy_identity_in_the_projects_resource_group(tmp_path):
    outputs = local_azure(tmp_path).ensure_bootstrap_stack(bootstrap_request())
    identity = (f"/subscriptions/{SUBSCRIPTION}/resourceGroups/rg-demo-dev/providers/"
                "Microsoft.ManagedIdentity/userAssignedIdentities/id-demo-dev-deploy")
    assert (outputs.deployer_identity, outputs.execution_identity, outputs.federation) == (
        identity, identity, str(uuid.uuid5(uuid.NAMESPACE_URL, identity)))


def test_bootstrap_records_the_federated_credential_subject(tmp_path):
    adapter = local_azure(tmp_path)
    adapter.ensure_bootstrap_stack(bootstrap_request())
    assert adapter.stacks()[0]["trust_subject"] == "repo:acme/demo-infra:environment:dev"


def test_azure_state_is_kept_apart(tmp_path):
    local_azure(tmp_path).delete_stack(SUBSCRIPTION, "eastus2", "demo")
    assert ((tmp_path / "azure" / "stack-operations.json").exists(), (tmp_path / "aws").exists()) == (True, False)


def test_blob_backups_go_to_a_backup_vault_in_their_region(tmp_path):
    backup = local_azure(tmp_path).backup("9a1e2b3c-0000-4000-8000-000000000001")
    point = backup.back_up(BackupSource(SUBSCRIPTION, "eastus2", "Microsoft.Storage/storageAccounts", "stuploads"))
    assert (point.vault, point.ref.startswith(f"{point.vault}/backupInstances/")) == (
        "/subscriptions/9a1e2b3c-0000-4000-8000-000000000001/resourceGroups/rg-cloudinfra-backup/providers/"
        "Microsoft.DataProtection/backupVaults/bv-teardown-eastus2", True)


def test_cosmos_exports_go_to_the_locked_container(tmp_path):
    backup = local_azure(tmp_path).backup("9a1e2b3c-0000-4000-8000-000000000001")
    point = backup.back_up(BackupSource(SUBSCRIPTION, "eastus2", "Microsoft.DocumentDB/databaseAccounts", "cosmos-orders"))
    assert point.vault.endswith("/blobServices/default/containers/cloudinfra-teardown")


def test_settings_name_the_azure_backup_subscription(settings):
    from app.config import Settings

    configured = Settings(**{**settings.model_dump(), "azure_backup_subscription": "backup-sub"})
    assert (configured.cloud_mode("azure"), configured.backup_accounts()["azure"]) == ("local", "backup-sub")


# ---- what is not there yet ----

@pytest.mark.parametrize("part, message", [
    ("project", "Projects on Azure are not available yet."),
    ("teardown", "Teardowns on Azure are not available yet."),
    ("resources", "Releases on Azure are not available yet."),
    ("landing_zone", "The Azure landing zone is not available yet."),
])
def test_parts_still_to_come_say_so(part, message):
    with pytest.raises(ValidationFailedError, match=re.escape(message)):
        getattr(provider(), part)()


def test_an_azure_project_preview_is_refused_clearly(client):
    response = client.post("/v1/projects:preview", json=request_dict(provider="azure"))
    assert (response.status_code, response.json()["detail"]) == (422, "Projects on Azure are not available yet.")
