"""Applying a Google Cloud landing zone (§22.10.6, MC-3d): the local stand-in, the registries it fills, and a project
that provisions into the vended projects and tears down into the landing zone's vault."""

import pytest

from app.adapters.factory import AdapterFactory
from app.config import Settings
from app.provisioning.worker import Worker
from app.readback.manifest import ManifestSigner
from tests.factories import TEST_DATABASE_URL
from tests.gcp_helpers import gcp_request
from tests.lz_factories import CATALOG
from tests.test_gcp_landing_zone import design, gcp_answers_dict, pid
from tests.test_lz_api import ALEX, BASE, RILEY

JORDAN = {"X-Actor": "jordan", "X-Roles": "developer"}
SAM = {"X-Actor": "sam", "X-Roles": "reviewer"}


def local_executor(tmp_path):
    from app.providers.gcp.landing_zone.local_executor import LocalGcpLandingZone

    return LocalGcpLandingZone(tmp_path)


# ---- the local stand-in ----

def test_project_ids_are_the_vended_projects(tmp_path):
    outputs = local_executor(tmp_path).apply(design())
    assert (outputs.accounts[pid("acme-payments-prod")], len(outputs.accounts)) == (
        pid("acme-payments-prod"), len(design().accounts()))


def test_each_environment_region_reports_its_shared_vpc_subnet(tmp_path):
    prod = next(network for network in local_executor(tmp_path).apply(design()).networks
                if (network.environment, network.region) == ("prod", "us-east4"))
    host = pid("acme-net-prod")
    assert (prod.network_ref, prod.subnet_refs, prod.firewall_ref, prod.account_names) == (
        f"projects/{host}/global/networks/vpc-prod", [f"projects/{host}/regions/us-east4/subnetworks/prod-us-east4"],
        "acme-prod", [pid("acme-payments-prod"), pid("acme-retail-prod")])


def test_the_vault_project_is_reported(tmp_path):
    assert local_executor(tmp_path).apply(design()).vault_account == pid("acme-vault")


def test_runs_are_recorded(tmp_path):
    executor = local_executor(tmp_path)
    executor.apply(design())
    assert (executor.history()[0]["deployments"][0], (tmp_path / "gcp").exists(), (tmp_path / "aws").exists()) == (
        "lz-foundation", True, False)


def test_empty_history(tmp_path):
    assert local_executor(tmp_path).history() == []


def test_the_factory_has_a_local_google_cloud_executor(settings):
    from app.providers.gcp.landing_zone.local_executor import LocalGcpLandingZone

    assert isinstance(AdapterFactory().landing_zone_executors(settings)["gcp"], LocalGcpLandingZone)


# ---- approval fills the registries ----

def gcp_request_body(**overrides) -> dict:
    return {"provider": "gcp", "answers": gcp_answers_dict(network={"egress": "local"}, **overrides), "edits": []}


def approved(client) -> dict:
    design_id = client.post(f"{BASE}/designs", json=gcp_request_body(), headers=ALEX).json()["id"]
    client.post(f"{BASE}/designs/{design_id}:submit", headers=ALEX)
    return client.post(f"{BASE}/designs/{design_id}:approve", json={"comment": "ok"}, headers=RILEY).json()


def test_approval_commits_the_google_cloud_repository(client):
    body = approved(client)
    assert (body["status"], body["repository"]) == ("applied", "acme-platform/landing-zone-gcp-infra")


def test_environments_are_bound_to_the_vended_projects(client, session):
    from app.registry.repository import RegistryRepository

    approved(client)
    session.expire_all()
    assert (RegistryRepository(session).account_for("gcp", "pf-payments", "prod"),
            RegistryRepository(session).account_for("aws", "pf-payments", "prod")) == (
        pid("acme-payments-prod"), "555555555555")


def test_shared_vpc_subnets_become_networks(client):
    approved(client)
    networks = client.get("/v1/admin/networks", params={"provider": "gcp",
                                                          "account_id": pid("acme-payments-prod")}).json()
    assert sorted((network["region"], network["is_default"]) for network in networks) == [
        ("us-east1", True), ("us-east4", True)]


def test_projects_per_product_are_not_bound(client, session):
    from app.registry.repository import RegistryRepository

    design_id = client.post(f"{BASE}/designs", json=gcp_request_body(account_model="product"), headers=ALEX).json()["id"]
    client.post(f"{BASE}/designs/{design_id}:submit", headers=ALEX)
    client.post(f"{BASE}/designs/{design_id}:approve", json={"comment": "ok"}, headers=RILEY)
    session.expire_all()
    assert RegistryRepository(session).account_for("gcp", "pf-payments", "prod") == "cloudinfra-payments-prod"


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


def test_a_project_provisions_into_the_vended_projects(client, settings, session_factory):
    approved(client)
    preview = client.post("/v1/projects:preview", json=gcp_request(attach=True)).json()
    assert (preview["targets"]["prod"]["account_id"], list(preview["targets"]["prod"]["networks"])) == (
        pid("acme-payments-prod"), ["us-east1"])


def test_teardown_backs_up_into_the_landing_zones_vault(client, settings, session_factory):
    approved(client)
    client.post("/v1/projects", json=gcp_request(), headers={"Idempotency-Key": "k1"})
    drain(settings, session_factory)
    body = client.post("/v1/projects/invoice-ingest/teardowns:preview",
                       json={"scope": "environment", "environments": ["dev"]}).json()
    assert (body["backup_account"], body["blockers"]) == (pid("acme-vault"), [])


def test_the_configured_vault_project_still_wins(session):
    from app.landing_zone.repository import LandingZoneRepository
    from app.teardown.backup_account import BackupAccountResolver

    assert BackupAccountResolver({"gcp": "override-vault"}, LandingZoneRepository(session)).resolve("gcp") == (
        "override-vault")


def test_designs_record_unit_owners():
    built = design()
    assert {account.owner for account in built.ou_named("PROD").accounts} == {"pf-payments", "pf-retail", None}


def test_catalog_is_the_registry():
    assert CATALOG.portfolios == ["pf-payments", "pf-retail"]
