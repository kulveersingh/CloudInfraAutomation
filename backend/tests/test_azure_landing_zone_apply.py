"""Applying an Azure landing zone (§22.12.6, MC-5c): the local stand-in, the registries it fills, and a project that
provisions into the vended subscriptions and tears down into the landing zone's backup subscription."""

import uuid

import pytest

from app.adapters.factory import AdapterFactory
from app.config import Settings
from app.provisioning.worker import Worker
from app.readback.manifest import ManifestSigner
from tests.azure_helpers import azure_request
from tests.factories import TEST_DATABASE_URL
from tests.test_azure_landing_zone import TENANT, azure_answers_dict, design
from tests.test_lz_api import ALEX, BASE, RILEY

GUID_NAMESPACE = uuid.NAMESPACE_URL


def subscription(name: str) -> str:
    return str(uuid.uuid5(GUID_NAMESPACE, f"cloudinfra:azure:{TENANT}:{name}"))


def local_executor(tmp_path):
    from app.providers.azure.landing_zone.local_executor import LocalAzureLandingZone

    return LocalAzureLandingZone(tmp_path)


# ---- the local stand-in ----

def test_subscription_ids_are_stable_guids_per_tenant_and_name(tmp_path):
    outputs = local_executor(tmp_path).apply(design())
    assert (outputs.accounts["acme-payments-prod"], len(outputs.accounts)) == (
        subscription("acme-payments-prod"), len(design().accounts()))


def test_each_spoke_reports_its_vnet_subnets_and_network_security_group(tmp_path):
    from app.networks.models import NetworkInput
    from app.providers.azure.networks import azure_network_problems

    spoke = next(network for network in local_executor(tmp_path).apply(design()).networks
                 if network.account_names == ["acme-payments-prod"] and network.region == "centralus")
    group = f"/subscriptions/{subscription('acme-payments-prod')}/resourceGroups/rg-network/providers/Microsoft.Network"
    registered = NetworkInput(provider="azure", name="spoke", account_id=subscription("acme-payments-prod"),
                              region=spoke.region, network_ref=spoke.network_ref, cidr=spoke.cidr,
                              subnet_refs=spoke.subnet_refs, firewall_refs=[spoke.firewall_ref])
    assert (spoke.environment, spoke.network_ref, spoke.subnet_refs, spoke.firewall_ref, spoke.label,
            azure_network_problems(registered)) == (
        "prod", f"{group}/virtualNetworks/vnet-centralus",
        [f"{group}/virtualNetworks/vnet-centralus/subnets/functions",
         f"{group}/virtualNetworks/vnet-centralus/subnets/endpoints"],
        f"{group}/networkSecurityGroups/nsg-centralus", "PROD", [])


def test_spoke_ranges_are_the_ones_the_stacks_deploy(tmp_path):
    from app.landing_zone.design import OrgCatalog
    from app.providers.azure.landing_zone.stacks.base import StackContext

    built = design()
    spokes = {(spoke.account, spoke.region): spoke.address
              for spoke in StackContext(built, OrgCatalog(portfolios=[], products=[])).spokes()}
    assert {(network.account_names[0], network.region): network.cidr
            for network in local_executor(tmp_path).apply(built).networks} == spokes


def test_the_backup_subscription_is_reported(tmp_path):
    assert local_executor(tmp_path).apply(design()).vault_account == "acme-backup"


def test_no_backup_subscription_reports_no_vault(tmp_path):
    built = design(infrastructure=["network", "shared_services"])
    assert local_executor(tmp_path).apply(built).vault_account is None


def test_runs_are_recorded(tmp_path):
    executor = local_executor(tmp_path)
    executor.apply(design())
    assert (executor.history()[0]["stacks"][0], (tmp_path / "azure").exists(), (tmp_path / "gcp").exists()) == (
        "lz-foundation", True, False)


def test_empty_history(tmp_path):
    assert local_executor(tmp_path).history() == []


def test_the_factory_has_a_local_azure_executor(settings):
    from app.providers.azure.landing_zone.local_executor import LocalAzureLandingZone

    assert isinstance(AdapterFactory().landing_zone_executors(settings)["azure"], LocalAzureLandingZone)


# ---- approval fills the registries ----

def azure_request_body(**overrides) -> dict:
    return {"provider": "azure", "answers": azure_answers_dict(**overrides), "edits": []}


def approved(client, **overrides) -> dict:
    design_id = client.post(f"{BASE}/designs", json=azure_request_body(**overrides), headers=ALEX).json()["id"]
    client.post(f"{BASE}/designs/{design_id}:submit", headers=ALEX)
    return client.post(f"{BASE}/designs/{design_id}:approve", json={"comment": "ok"}, headers=RILEY).json()


def test_approval_commits_the_azure_repository(client):
    body = approved(client)
    assert (body["status"], body["repository"], body["accounts"]["acme-backup"]) == (
        "applied", "acme-platform/landing-zone-azure-infra", subscription("acme-backup"))


def test_environments_are_bound_to_the_vended_subscriptions(client, session):
    from app.registry.repository import RegistryRepository

    approved(client)
    session.expire_all()
    assert RegistryRepository(session).account_for("azure", "pf-payments", "prod") == subscription("acme-payments-prod")


def test_spokes_become_networks(client):
    approved(client)
    networks = client.get("/v1/admin/networks", params={"provider": "azure",
                                                          "account_id": subscription("acme-payments-prod")}).json()
    assert sorted((network["region"], network["is_default"]) for network in networks) == [
        ("centralus", True), ("eastus2", True)]


# ---- a project on the landing zone ----

@pytest.fixture
def settings(tmp_path):
    return Settings(database_url=TEST_DATABASE_URL, local_state_dir=str(tmp_path), worker_poll_seconds=0)


def drain(settings, session_factory) -> None:
    factory = AdapterFactory()
    worker = Worker(session_factory, factory.github(settings), factory.clouds(settings), settings.github_owner,
                    ManifestSigner.from_settings(settings))
    while worker.process_one():
        pass


def test_a_project_provisions_into_the_vended_subscriptions_and_their_spokes(client):
    approved(client)
    preview = client.post("/v1/projects:preview", json=azure_request(attach=True)).json()
    assert (preview["targets"]["prod"]["account_id"], list(preview["targets"]["prod"]["networks"])) == (
        subscription("acme-payments-prod"), ["eastus2"])


def test_teardown_backs_up_into_the_landing_zones_backup_subscription(client, settings, session_factory):
    approved(client)
    client.post("/v1/projects", json=azure_request(), headers={"Idempotency-Key": "k1"})
    drain(settings, session_factory)
    body = client.post("/v1/projects/invoice-ingest/teardowns:preview",
                       json={"scope": "environment", "environments": ["dev"]}).json()
    assert (body["backup_account"], body["blockers"]) == (subscription("acme-backup"), [])


def test_the_applied_azure_landing_zone_reads_back_from_its_repository(client):
    applied = approved(client)
    result = client.get(f"{BASE}/repository:read-back", params={"provider": "azure"}, headers=ALEX).json()
    assert (result["verified"], result["findings"], result["commit_sha"], result["request"]["provider"],
            result["request"]["answers"]["provider_answers"]["tenant_id"]) == (
        True, [], applied["commit_sha"], "azure", TENANT)
