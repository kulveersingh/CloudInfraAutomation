import pytest
from sqlalchemy.exc import IntegrityError

from app.db import models
from app.errors import NotFoundError
from app.providers.aws.provider import AwsProvider
from app.providers.base import CloudProvider, ProviderRegistry, Vocabulary
from tests.factories import request_dict
from tests.lz_factories import answers_dict

ALEX = {"X-Actor": "alex", "X-Roles": "platform-admin"}


class ExampleProvider(CloudProvider):
    id = "example"
    name = "Example Cloud"

    def vocabulary(self):
        return AwsProvider().vocabulary()

    def default_regions(self):
        return ("north-1", "south-1")

    def project(self):
        return AwsProvider().project()

    def teardown(self):
        return AwsProvider().teardown()

    def resources(self):
        return AwsProvider().resources()


# ---- registry ----

def test_default_registry_has_aws_only():
    assert [provider.id for provider in ProviderRegistry.default().all()] == ["aws"]


def test_registry_finds_a_provider_by_id():
    assert isinstance(ProviderRegistry.default().get("aws"), AwsProvider)


def test_unknown_provider():
    with pytest.raises(NotFoundError, match="Unknown cloud provider 'gcp'"):
        ProviderRegistry.default().get("gcp")


def test_new_providers_register_without_changing_the_core():
    registry = ProviderRegistry.default()
    registry.register(ExampleProvider())
    assert (registry.has("example"), [provider.id for provider in registry.all()]) == (True, ["aws", "example"])


# ---- AWS provider ----

def test_aws_vocabulary():
    assert AwsProvider().vocabulary() == Vocabulary(
        isolation_unit="account", hierarchy_node="OU", iac_document="CloudFormation template", deploy_unit="stack",
        preventive_policy="SCP", private_network="VPC", landing_zone_service="Control Tower",
        control_catalog="Control Tower controls")


def test_aws_default_regions():
    assert AwsProvider().default_regions() == ("us-east-1", "us-east-2")


def test_provider_description():
    description = AwsProvider().describe()
    assert (description["id"], description["name"], description["default_regions"],
            description["vocabulary"]["isolation_unit"]) == (
        "aws", "Amazon Web Services", {"primary": "us-east-1", "secondary": "us-east-2"}, "account")


# ---- API ----

def test_providers_api(client):
    assert [provider["id"] for provider in client.get("/v1/providers").json()] == ["aws"]


def test_regions_belong_to_a_provider(client):
    assert {region["provider"] for region in client.get("/v1/admin/regions").json()} == {"aws"}


def test_regions_can_be_listed_per_provider(client):
    assert client.get("/v1/admin/regions", params={"provider": "example"}).json() == []


def test_region_update_names_the_provider(client):
    response = client.put("/v1/admin/regions/ap-southeast-2", params={"provider": "aws"}, json={"enabled": True})
    assert (response.json()["provider"], response.json()["enabled"]) == ("aws", True)


def test_region_of_another_provider_is_not_found(client):
    response = client.put("/v1/admin/regions/ap-southeast-2", params={"provider": "example"}, json={"enabled": True})
    assert response.status_code == 404


# ---- projects ----

def test_requests_default_to_aws(client):
    client.post("/v1/projects", json=request_dict(), headers={"Idempotency-Key": "k1"})
    assert client.get("/v1/projects").json()[0]["provider"] == "aws"


def test_unknown_provider_is_rejected(client):
    response = client.post("/v1/projects:preview", json=request_dict(provider="gcp"))
    assert (response.status_code, response.json()["detail"]) == (422, "Unknown cloud provider 'gcp'.")


def test_project_row_records_the_provider(client, session_factory):
    client.post("/v1/projects", json=request_dict(), headers={"Idempotency-Key": "k1"})
    with session_factory() as session:
        assert session.get(models.Project, "invoice-ingest").provider == "aws"


# ---- landing zone ----

def test_landing_zone_designs_record_the_provider(client):
    design = client.post("/v1/admin/landing-zone/designs", json={"answers": answers_dict(), "edits": []},
                         headers=ALEX).json()
    assert design["provider"] == "aws"


# ---- isolation units of other clouds fit ----

def test_account_bindings_hold_any_cloud_id(seeded):
    seeded.add(models.AccountBinding(environment_id="dev", portfolio_id="pf-payments", provider="example",
                                     account_id="0f8fad5b-d9cb-469f-a165-70867728950e"))
    seeded.commit()
    assert seeded.query(models.AccountBinding).filter_by(provider="example").one().account_id.startswith("0f8fad5b")


def test_account_ids_are_unique_per_provider(seeded):
    seeded.add(models.AccountBinding(environment_id="sandbox", portfolio_id="pf-retail", provider="aws",
                                     account_id="222222222222"))
    with pytest.raises(IntegrityError):
        seeded.commit()
