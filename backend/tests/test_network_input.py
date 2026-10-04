import pytest
from pydantic import ValidationError

from app.networks.models import NetworkInput

VALID = {
    "name": "Org shared VPC", "account_id": "222222222222", "region": "us-east-1",
    "vpc_id": "vpc-0a1b2c3d4e5f60718", "cidr": "10.20.0.0/16",
    "private_subnet_ids": ["subnet-0a1b2c3d4e5f60718", "subnet-0a1b2c3d4e5f60719"],
    "security_group_ids": ["sg-0a1b2c3d4e5f60718"], "is_default": True,
}


def network(**overrides) -> NetworkInput:
    return NetworkInput.model_validate({**VALID, **overrides})


def test_valid_network():
    assert network().vpc_id == "vpc-0a1b2c3d4e5f60718"


@pytest.mark.parametrize(("field", "value"), [
    ("vpc_id", "vpc-xyz"), ("account_id", "1234"), ("security_group_ids", ["group-1"]),
    ("private_subnet_ids", ["subnet-0a1b2c3d4e5f60718", "net-1"]), ("security_group_ids", [])])
def test_malformed_values_are_rejected(field, value):
    with pytest.raises(ValidationError):
        network(**{field: value})


def test_needs_two_private_subnets():
    with pytest.raises(ValidationError, match="at least two private subnets"):
        network(private_subnet_ids=["subnet-0a1b2c3d4e5f60718"])


def test_cidr_must_be_private():
    with pytest.raises(ValidationError, match="must be a private range"):
        network(cidr="54.10.0.0/16")


def test_cidr_must_be_a_network():
    with pytest.raises(ValidationError):
        network(cidr="not-a-cidr")
