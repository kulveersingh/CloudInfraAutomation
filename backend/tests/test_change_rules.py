import pytest

from app.projects.change_rules import ChangeRules
from app.synth.request import ProjectRequest
from tests.factories import dr_request_dict, request_dict


def problems(proposed: dict, current: dict | None = None) -> list[str]:
    return ChangeRules.default().problems(ProjectRequest.model_validate(current or request_dict()),
                                          ProjectRequest.model_validate(proposed))


def added_table(**overrides) -> dict:
    proposed = request_dict(**overrides)
    proposed["resources"].append({"id": "orders", "type": "dynamodb.table"})
    return proposed


def test_adding_a_service_is_allowed():
    assert problems(added_table()) == []


def test_changing_settings_connections_and_network_is_allowed():
    proposed = request_dict(connections=[], network={"attach_compute": False, "selections": {}})
    proposed["resources"][1]["config"] = {"memory_mb": 512}
    assert problems(proposed) == []


def test_adding_an_environment_is_allowed():
    assert problems(added_table(environments=["sandbox", "dev", "test", "stage", "prod"])) == []


@pytest.mark.parametrize("change, message", [
    ({"project_name": "other-name"}, "The project name cannot change."),
    ({"ownership": {"portfolio_id": "pf-retail", "product_id": "pr-invoicing",
                    "data_classification": "confidential"}}, "The portfolio cannot change."),
    ({"ownership": {"portfolio_id": "pf-payments", "product_id": "pl-payments-core",
                    "data_classification": "confidential"}}, "The product cannot change."),
    ({"ownership": {"portfolio_id": "pf-payments", "product_id": "pr-invoicing",
                    "data_classification": "restricted"}}, "The data classification cannot change."),
])
def test_locked_fields(change, message):
    assert problems(added_table(**change)) == [message]


def test_resilience_is_locked():
    assert problems(dr_request_dict(resources=added_table()["resources"])) == [
        "The resilience mode and regions cannot change."]


def test_environments_can_only_be_added():
    assert problems(added_table(environments=["dev", "prod"])) == [
        "Environments can only be added; removing test, stage is not supported yet."]


def test_a_change_must_change_something():
    assert problems(request_dict()) == ["Nothing changed."]


def test_reordering_environments_alone_is_not_a_change():
    assert problems(request_dict(environments=["prod", "stage", "test", "dev"])) == ["Nothing changed."]
