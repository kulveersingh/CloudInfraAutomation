from tests.factories import request_dict
from tests.test_network_input import VALID


def test_list_networks(client):
    assert len(client.get("/v1/admin/networks", params={"account_id": "555555555555"}).json()) == 2


def test_create_network(client):
    response = client.post("/v1/admin/networks", json={**VALID, "is_default": False})
    assert (response.status_code, response.json()["cidr"]) == (201, "10.20.0.0/16")


def test_create_rejects_public_cidr(client):
    assert client.post("/v1/admin/networks", json={**VALID, "cidr": "54.0.0.0/16"}).status_code == 422


def test_update_network(client):
    network_id = client.get("/v1/admin/networks").json()[0]["id"]
    response = client.put(f"/v1/admin/networks/{network_id}", json={**VALID, "name": "Core VPC"})
    assert response.json()["name"] == "Core VPC"


def test_update_unknown_network(client):
    assert client.put("/v1/admin/networks/net-missing", json=VALID).status_code == 404


def test_network_settings(client):
    client.put("/v1/admin/network-settings", json={"attach_compute_by_default": False})
    assert client.get("/v1/admin/network-settings").json() == {"attach_compute_by_default": False}


def test_wizard_options(client):
    options = client.get("/v1/networks/options", params={"portfolio_id": "pf-payments"}).json()
    assert {"environment", "region", "account_id", "networks", "default_network_id"} <= set(options[0])


def test_preview_shows_selected_networks(client):
    targets = client.post("/v1/projects:preview", json=request_dict()).json()["targets"]
    assert targets["prod"]["networks"]["us-east-1"]["vpc_id"].startswith("vpc-")


def test_preview_without_vpc_attachment_has_no_networks(client):
    targets = client.post("/v1/projects:preview", json=request_dict(network={"attach_compute": False})).json()[
        "targets"]
    assert targets["prod"]["networks"] == {}


def test_preview_fails_when_a_region_has_no_network(client):
    payload = request_dict(resilience={"mode": "single", "primary_region": "us-west-2", "secondary_region": None})
    response = client.post("/v1/projects:preview", json=payload)
    assert (response.status_code, "No network configured" in response.json()["detail"]) == (422, True)
