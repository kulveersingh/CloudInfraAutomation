import pytest

from app.errors import NotFoundError, ValidationFailedError
from app.networks.models import NetworkInput
from app.networks.service import NetworkService
from app.provisioning.topology import TopologyFactory
from app.synth.request import ProjectRequest
from tests.factories import dr_request_dict, request_dict
from tests.test_network_input import VALID


@pytest.fixture
def service(seeded) -> NetworkService:
    return NetworkService.for_session(seeded)


def resolve(service: NetworkService, payload: dict):
    request = ProjectRequest.model_validate(payload)
    accounts = {"dev": "222222222222", "test": "333333333333", "stage": "444444444444", "prod": "555555555555"}
    return service.resolve(request, TopologyFactory.default().for_resilience(request.resilience), accounts)


def test_seed_provides_networks_for_default_regions(service):
    assert len(service.networks()) == 60  # 30 AWS VPCs and 30 Google Cloud Shared VPC subnets


def test_filter_by_account_and_region(service):
    networks = service.networks(account_id="555555555555", region="us-east-2")
    assert [(item["account_id"], item["region"], item["is_default"]) for item in networks] == [
        ("555555555555", "us-east-2", True)]


def test_create_network(service):
    created = service.create(NetworkInput.model_validate({**VALID, "is_default": False}))
    assert created["network_ref"] == "vpc-0a1b2c3d4e5f60718"


def test_new_default_replaces_old_default(service):
    created = service.create(NetworkInput.model_validate(VALID))
    defaults = [item["id"] for item in service.networks("222222222222", "us-east-1") if item["is_default"]]
    assert defaults == [created["id"]]


def test_update_network(service):
    network_id = service.networks("222222222222", "us-east-1")[0]["id"]
    updated = service.update(network_id, NetworkInput.model_validate({**VALID, "name": "Renamed"}))
    assert updated["name"] == "Renamed"


def test_update_unknown_network(service):
    with pytest.raises(NotFoundError):
        service.update("net-missing", NetworkInput.model_validate(VALID))


def test_settings_default_to_attaching_compute(service):
    assert service.settings() == {"attach_compute_by_default": True}


def test_settings_can_change(service):
    service.update_settings(False)
    assert service.settings() == {"attach_compute_by_default": False}


def test_options_cover_every_environment_and_enabled_region(service):
    options = service.options("pf-payments")
    assert len(options) == 5 * 5


def test_option_lists_default_network(service):
    option = next(item for item in service.options("pf-payments")
                  if (item["environment"], item["region"]) == ("prod", "us-east-1"))
    assert (option["account_id"], option["default_network_id"]) == ("555555555555", option["networks"][0]["id"])


def test_option_without_network_has_no_default(service):
    option = next(item for item in service.options("pf-payments")
                  if (item["environment"], item["region"]) == ("prod", "us-west-2"))
    assert (option["networks"], option["default_network_id"]) == ([], None)


def test_resolve_uses_default_networks(service):
    networks = resolve(service, request_dict())
    assert networks[("prod", "us-east-1")]["account_id"] == "555555555555"


def test_resolve_covers_secondary_region_for_dr(service):
    assert ("prod", "us-east-2") in resolve(service, dr_request_dict())


def test_resolve_honours_selection(service):
    created = service.create(NetworkInput.model_validate({**VALID, "account_id": "555555555555", "is_default": False}))
    payload = request_dict(network={"attach_compute": True, "selections": {"prod:us-east-1": created["id"]}})
    assert resolve(service, payload)[("prod", "us-east-1")]["id"] == created["id"]


def test_selection_from_another_account_is_rejected(service):
    other = service.networks("222222222222", "us-east-1")[0]["id"]
    payload = request_dict(network={"attach_compute": True, "selections": {"prod:us-east-1": other}})
    with pytest.raises(ValidationFailedError, match="does not belong to account 555555555555 in us-east-1"):
        resolve(service, payload)


def test_unknown_selection_is_rejected(service):
    payload = request_dict(network={"attach_compute": True, "selections": {"prod:us-east-1": "net-missing"}})
    with pytest.raises(ValidationFailedError, match="Unknown network 'net-missing'"):
        resolve(service, payload)


def test_missing_network_is_reported(service):
    payload = request_dict(resilience={"mode": "single", "primary_region": "us-west-2", "secondary_region": None})
    with pytest.raises(ValidationFailedError, match="No network configured for dev in us-west-2"):
        resolve(service, payload)


def test_nothing_to_resolve_without_vpc_attachment(service):
    payload = request_dict(network={"attach_compute": False})
    assert resolve(service, payload) == {}
