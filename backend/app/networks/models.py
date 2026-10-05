import ipaddress

from pydantic import BaseModel, Field, field_validator, model_validator

from app.providers.base import DEFAULT_PROVIDER, ProviderRegistry, unknown_provider

MIN_PRIVATE_SUBNETS = 2


class NetworkInput(BaseModel):
    """What a platform engineer enters for an organization network. The cloud checks its own id formats."""

    provider: str = DEFAULT_PROVIDER
    name: str = Field(min_length=1, max_length=128)
    account_id: str = Field(min_length=1, max_length=64)
    region: str = Field(min_length=1)
    network_ref: str = Field(min_length=1, max_length=255)
    cidr: str
    subnet_refs: list[str]
    firewall_refs: list[str] = Field(min_length=1)
    is_default: bool = False

    @field_validator("subnet_refs")
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

    @model_validator(mode="after")
    def fits_the_cloud(self) -> "NetworkInput":
        providers = ProviderRegistry.default()
        if not providers.has(self.provider):
            raise ValueError(unknown_provider(self.provider))
        problems = providers.get(self.provider).network_problems(self)
        if problems:
            raise ValueError(" ".join(problems))
        return self
