import re

import pytest
from pydantic import ValidationError

from app.networks.models import NetworkInput

VALID = {
    "name": "Org shared VPC", "account_id": "222222222222", "region": "us-east-1",
    "network_ref": "vpc-0a1b2c3d4e5f60718", "cidr": "10.20.0.0/16",
    "subnet_refs": ["subnet-0a1b2c3d4e5f60718", "subnet-0a1b2c3d4e5f60719"],
    "firewall_refs": ["sg-0a1b2c3d4e5f60718"], "is_default": True,
}


def network(**overrides) -> NetworkInput:
    return NetworkInput.model_validate({**VALID, **overrides})


def test_valid_network():
    assert network().network_ref == "vpc-0a1b2c3d4e5f60718"


@pytest.mark.parametrize(("field", "value"), [
    ("network_ref", "vpc-xyz"), ("account_id", "1234"), ("firewall_refs", ["group-1"]),
    ("subnet_refs", ["subnet-0a1b2c3d4e5f60718", "net-1"]), ("firewall_refs", [])])
def test_malformed_values_are_rejected(field, value):
    with pytest.raises(ValidationError):
        network(**{field: value})


def test_needs_two_private_subnets():
    with pytest.raises(ValidationError, match="at least two private subnets"):
        network(subnet_refs=["subnet-0a1b2c3d4e5f60718"])


def test_cidr_must_be_private():
    with pytest.raises(ValidationError, match="must be a private range"):
        network(cidr="54.10.0.0/16")


def test_cidr_must_be_a_network():
    with pytest.raises(ValidationError):
        network(cidr="not-a-cidr")


@pytest.mark.parametrize(("field", "value", "message"), [
    ("account_id", "1234", "AWS account ids are 12 digits."),
    ("network_ref", "vpc-xyz", "'vpc-xyz' is not a VPC id (vpc-…)."),
    ("subnet_refs", ["subnet-0a1b2c3d4e5f60718", "net-1"], "'net-1' is not a subnet id (subnet-…)."),
    ("firewall_refs", ["group-1"], "'group-1' is not a security group id (sg-…)."),
])
def test_aws_networks_explain_what_is_wrong(field, value, message):
    with pytest.raises(ValidationError, match=re.escape(message)):
        network(**{field: value})


def test_networks_default_to_aws():
    assert network().provider == "aws"


def test_networks_of_an_unknown_provider_are_rejected():
    with pytest.raises(ValidationError, match="Unknown cloud provider 'gcp'"):
        network(provider="gcp")
