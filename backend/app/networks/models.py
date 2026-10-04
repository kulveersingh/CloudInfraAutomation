import ipaddress
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, field_validator

MIN_PRIVATE_SUBNETS = 2
AccountId = Annotated[str, StringConstraints(pattern=r"^[0-9]{12}$")]
VpcId = Annotated[str, StringConstraints(pattern=r"^vpc-[0-9a-f]{8,17}$")]
SubnetId = Annotated[str, StringConstraints(pattern=r"^subnet-[0-9a-f]{8,17}$")]
SecurityGroupId = Annotated[str, StringConstraints(pattern=r"^sg-[0-9a-f]{8,17}$")]


class NetworkInput(BaseModel):
    """What a platform engineer enters for an organization network."""

    name: str = Field(min_length=1, max_length=128)
    account_id: AccountId
    region: str = Field(min_length=1)
    vpc_id: VpcId
    cidr: str
    private_subnet_ids: list[SubnetId]
    security_group_ids: list[SecurityGroupId] = Field(min_length=1)
    is_default: bool = False

    @field_validator("private_subnet_ids")
    @classmethod
    def enough_subnets(cls, subnets: list[str]) -> list[str]:
        if len(subnets) < MIN_PRIVATE_SUBNETS:
            raise ValueError("Use at least two private subnets in different availability zones.")
        return subnets

    @field_validator("cidr")
    @classmethod
    def private_range(cls, cidr: str) -> str:
        if not ipaddress.ip_network(cidr, strict=False).is_private:
            raise ValueError(f"{cidr} must be a private range.")
        return cidr
