import ipaddress

import pytest

from app.landing_zone.ipam import AddressSpaceTooSmallError, IpamPlanner

SLOTS = ["sandbox", "dev", "test", "stage", "prod", "shared"]


def plan(cidr="10.0.0.0/8", regions=("us-east-1", "us-east-2"), slots=SLOTS):
    return IpamPlanner().plan(cidr, list(regions), list(slots))


def test_one_pool_per_region_per_slot():
    assert len(plan().pools) == 12


def test_regions_get_separate_halves():
    assert plan().regional == {"us-east-1": "10.0.0.0/9", "us-east-2": "10.128.0.0/9"}


def test_slots_split_each_region_evenly():
    assert plan().pool("us-east-1", "prod") == "10.64.0.0/12"


def test_pools_never_overlap():
    networks = [ipaddress.ip_network(cidr) for cidr in plan().pools.values()]
    assert not any(a.overlaps(b) for i, a in enumerate(networks) for b in networks[i + 1:])


def test_three_regions_round_up_to_quarters():
    assert plan(regions=("us-east-1", "us-east-2", "us-west-2")).regional["us-west-2"] == "10.128.0.0/10"


def test_too_small_address_space_is_rejected():
    with pytest.raises(AddressSpaceTooSmallError):
        plan(cidr="10.0.0.0/22")
