import pytest
from pydantic import ValidationError

from app.landing_zone.answers import LandingZoneAnswers
from tests.lz_factories import answers, answers_dict


def invalid(**overrides) -> bool:
    with pytest.raises(ValidationError):
        LandingZoneAnswers.model_validate(answers_dict(**overrides))
    return True


def test_five_environments_by_default():
    assert [environment.name for environment in answers().environments()] == ["Sandbox", "DEV", "TEST", "STAGE", "PROD"]


def test_four_environments_fold_testing_into_dev():
    assert [environment.id for environment in answers(environment_count=4).environments()] == [
        "sandbox", "dev", "stage", "prod"]


def test_six_environments_add_uat():
    assert [environment.id for environment in answers(environment_count=6).environments()] == [
        "sandbox", "dev", "test", "uat", "stage", "prod"]


def test_stage_and_prod_are_production_tier():
    assert [environment.id for environment in answers().environments() if environment.tier == "prod"] == [
        "stage", "prod"]


def test_environments_can_be_renamed():
    names = [environment.name for environment in answers(environment_names={"stage": "QA"}).environments()]
    assert names == ["Sandbox", "DEV", "TEST", "QA", "PROD"]


def test_other_environment_counts_are_rejected():
    assert invalid(environment_count=3)


def test_renaming_an_unknown_environment_is_rejected():
    assert invalid(environment_names={"uat": "UAT"})


def test_duplicate_environment_names_are_rejected():
    assert invalid(environment_names={"test": "DEV"})


def test_environment_names_are_short_identifiers():
    assert invalid(environment_names={"test": "Test env!"})


def test_defaults_follow_the_recommendations():
    defaults = answers()
    assert (defaults.grouping, defaults.account_model, defaults.controls_profile, defaults.network.egress) == (
        "separate", "portfolio", "recommended", "central")


def test_organization_name_is_lowercase():
    assert invalid(organization_name="Acme")


def test_management_email_is_checked():
    assert invalid(management_email="not-an-email")


def test_at_least_two_governed_regions():
    assert invalid(governed_regions=["us-east-1"])


def test_governed_regions_are_unique():
    assert invalid(governed_regions=["us-east-1", "us-east-1"])


def test_home_region_must_be_governed():
    assert invalid(home_region="eu-west-1")


def test_organization_cidr_must_be_private():
    assert invalid(network={"cidr": "8.0.0.0/8"})


def test_organization_cidr_must_leave_room_for_vpcs():
    assert invalid(network={"cidr": "10.0.0.0/20"})


def test_hub_needs_the_network_account():
    assert invalid(infrastructure=["shared_services"])


def test_isolated_vpcs_do_not_need_the_network_account():
    assert answers(infrastructure=["shared_services"], network={"hub": False}).network.hub is False


def flow(**overrides) -> dict:
    return {"source": "dev", "destination": "test", "protocol": "tcp", "port": 5432, "reason": "Data refresh",
            **overrides}


def test_cross_environment_flow_is_accepted():
    assert answers(network={"flows": [flow()]}).network.flows[0].port == 5432


def test_flow_needs_known_environments():
    assert invalid(network={"flows": [flow(destination="uat")]})


def test_flow_cannot_stay_inside_one_environment():
    assert invalid(network={"flows": [flow(destination="dev")]})


def test_sandbox_has_no_flows():
    assert invalid(network={"flows": [flow(source="sandbox")]})


def test_flow_ports_are_single_valid_ports():
    assert invalid(network={"flows": [flow(port=70000)]})


def test_flows_need_inspection():
    assert invalid(network={"inspection": False, "flows": [flow()]})


def test_flows_need_the_hub():
    assert invalid(infrastructure=["shared_services"], network={"hub": False, "flows": [flow()]})


def test_sandbox_budget_is_positive():
    assert invalid(sandbox={"monthly_budget_usd": 0})
