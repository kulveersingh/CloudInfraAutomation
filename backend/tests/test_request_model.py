import pytest
from pydantic import ValidationError

from app.synth.request import ProjectRequest
from tests.factories import request_dict


def parse(payload: dict) -> ProjectRequest:
    return ProjectRequest.model_validate(payload)


def test_valid_request_parses():
    assert parse(request_dict()).project_name == "invoice-ingest"


def test_event_notify_defaults_to_object_created():
    assert parse(request_dict()).connections[0].events == ["s3:ObjectCreated:*"]


def test_resource_lookup_by_id():
    assert parse(request_dict()).resource("processor").type == "lambda.function"


def test_resource_lookup_unknown_id_returns_none():
    assert parse(request_dict()).resource("missing") is None


@pytest.mark.parametrize("name", ["ab", "Invoice", "a--b", "trailing-", "1abc", "x" * 31])
def test_invalid_project_names_are_rejected(name):
    with pytest.raises(ValidationError):
        parse(request_dict(project_name=name))


def test_invalid_resource_id_is_rejected():
    with pytest.raises(ValidationError):
        parse(request_dict(resources=[{"id": "Bad_ID", "type": "s3.bucket"}], connections=[]))


def test_unknown_classification_is_rejected():
    ownership = {"portfolio_id": "pf-payments", "product_id": "pr-invoicing", "data_classification": "secret"}
    with pytest.raises(ValidationError):
        parse(request_dict(ownership=ownership))


def test_at_least_one_environment_required():
    with pytest.raises(ValidationError):
        parse(request_dict(environments=[]))


def test_at_least_one_resource_required():
    with pytest.raises(ValidationError):
        parse(request_dict(resources=[], connections=[]))


def test_at_most_twenty_resources():
    resources = [{"id": f"q{index}", "type": "sqs.queue"} for index in range(21)]
    with pytest.raises(ValidationError):
        parse(request_dict(resources=resources, connections=[]))


def test_unknown_resilience_mode_is_rejected():
    with pytest.raises(ValidationError):
        parse(request_dict(resilience={"mode": "multi", "primary_region": "us-east-1"}))


def test_network_defaults_to_attaching_compute():
    assert parse(request_dict()).network.attach_compute is True


def test_network_selection_keys_must_be_environment_and_region():
    with pytest.raises(ValidationError):
        parse(request_dict(network={"attach_compute": True, "selections": {"prod": "net-1"}}))
