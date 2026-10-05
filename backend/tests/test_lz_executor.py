import re

from app.landing_zone.designer import LandingZoneDesigner
from app.providers.aws.landing_zone.local_executor import LocalLandingZoneExecutor
from tests.lz_factories import CATALOG, account_op, add_ou, answers, edited


def apply(tmp_path, **overrides):
    design = LandingZoneDesigner.default().design(answers(**overrides), CATALOG)
    return LocalLandingZoneExecutor(tmp_path).apply(design)


def test_every_account_gets_a_twelve_digit_id(tmp_path):
    outputs = apply(tmp_path)
    assert all(re.fullmatch(r"\d{12}", account_id) for account_id in outputs.accounts.values())


def test_account_ids_are_stable(tmp_path):
    assert apply(tmp_path).accounts == apply(tmp_path).accounts


def test_one_network_per_environment_per_region(tmp_path):
    networks = apply(tmp_path).networks
    assert sorted({(network.environment, network.region) for network in networks}) == sorted(
        (environment, region) for environment in ("sandbox", "dev", "test", "stage", "prod")
        for region in ("us-east-1", "us-east-2"))


def test_network_uses_the_planned_cidr(tmp_path):
    prod = next(network for network in apply(tmp_path).networks
                if (network.environment, network.region) == ("prod", "us-east-1"))
    assert prod.cidr == "10.64.0.0/16"


def test_network_lists_the_accounts_that_share_it(tmp_path):
    prod = next(network for network in apply(tmp_path).networks if network.environment == "prod")
    assert prod.account_names == ["acme-payments-prod", "acme-retail-prod"]


def test_network_ids_look_like_aws_ids(tmp_path):
    network = apply(tmp_path).networks[0]
    assert (network.network_ref.startswith("vpc-"), len(network.subnet_refs), network.firewall_ref.startswith("sg-")) == (
        True, 2, True)


def test_runs_are_recorded(tmp_path):
    executor = LocalLandingZoneExecutor(tmp_path)
    executor.apply(LandingZoneDesigner.default().design(answers(), CATALOG))
    assert executor.history()[0]["stacks"] == ["lz-foundation", "lz-structure", "lz-accounts", "lz-network",
                                               "lz-backup", "lz-bootstrap"]


def test_empty_history(tmp_path):
    assert LocalLandingZoneExecutor(tmp_path).history() == []


def apply_edited(tmp_path, edits):
    return LocalLandingZoneExecutor(tmp_path).apply(edited(edits)[0])


def test_accounts_in_child_ous_share_the_environment_network(tmp_path):
    edits = [add_ou("Payments"), account_op("move_account", "acme-payments-prod", ou="custom_payments")]
    prod = next(network for network in apply_edited(tmp_path, edits).networks if network.environment == "prod")
    assert prod.account_names == ["acme-retail-prod", "acme-payments-prod"]


def test_disabled_accounts_get_no_id_and_no_network(tmp_path):
    outputs = apply_edited(tmp_path, [account_op("disable_account", "acme-retail-prod")])
    names = [name for network in outputs.networks for name in network.account_names]
    assert ("acme-retail-prod" in outputs.accounts, "acme-retail-prod" in names) == (False, False)
