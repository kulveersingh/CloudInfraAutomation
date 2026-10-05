import re

ACCOUNT_ID = re.compile(r"^[0-9]{12}$")
VPC_ID = re.compile(r"^vpc-[0-9a-f]{8,17}$")
SUBNET_ID = re.compile(r"^subnet-[0-9a-f]{8,17}$")
SECURITY_GROUP_ID = re.compile(r"^sg-[0-9a-f]{8,17}$")
MIN_PRIVATE_SUBNETS = 2  # subnets are per availability zone on AWS


def aws_network_problems(network) -> list[str]:
    """An AWS organization network: a 12-digit account, a VPC, its subnets and its security groups."""
    problems = [] if ACCOUNT_ID.match(network.account_id) else ["AWS account ids are 12 digits."]
    problems += [] if VPC_ID.match(network.network_ref) else [f"'{network.network_ref}' is not a VPC id (vpc-…)."]
    problems += [f"'{subnet}' is not a subnet id (subnet-…)." for subnet in network.subnet_refs
                 if not SUBNET_ID.match(subnet)]
    if len(network.subnet_refs) < MIN_PRIVATE_SUBNETS:
        problems.append("Use at least two private subnets in different availability zones.")
    return problems + [f"'{group}' is not a security group id (sg-…)." for group in network.firewall_refs
                       if not SECURITY_GROUP_ID.match(group)]
