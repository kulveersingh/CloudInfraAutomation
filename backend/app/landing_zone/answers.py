import ipaddress
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

EnvironmentTier = Literal["sandbox", "nonprod", "prod"]
InfrastructureAccount = Literal["network", "shared_services", "identity", "backup", "monitoring", "cicd"]
OptionalOu = Literal["exceptions", "suspended", "individual_business_users"]
ComplianceScope = Literal["PCI", "HIPAA", "GxP"]

ENVIRONMENT_NAME_PATTERN = r"^[A-Za-z][A-Za-z0-9-]{1,15}$"
LARGEST_ORGANIZATION_PREFIX = 16
DEFAULT_INFRASTRUCTURE = ["network", "shared_services", "identity", "backup", "monitoring"]


class EnvironmentAnswer(BaseModel):
    id: str
    name: str
    tier: EnvironmentTier


_SANDBOX = EnvironmentAnswer(id="sandbox", name="Sandbox", tier="sandbox")
_DEV = EnvironmentAnswer(id="dev", name="DEV", tier="nonprod")
_TEST = EnvironmentAnswer(id="test", name="TEST", tier="nonprod")
_UAT = EnvironmentAnswer(id="uat", name="UAT", tier="nonprod")
_STAGE = EnvironmentAnswer(id="stage", name="STAGE", tier="prod")
_PROD = EnvironmentAnswer(id="prod", name="PROD", tier="prod")

ENVIRONMENT_PRESETS: dict[int, list[EnvironmentAnswer]] = {
    4: [_SANDBOX, _DEV, _STAGE, _PROD],
    5: [_SANDBOX, _DEV, _TEST, _STAGE, _PROD],
    6: [_SANDBOX, _DEV, _TEST, _UAT, _STAGE, _PROD],
}


class FlowException(BaseModel):
    """A single declared, inspected network flow between two environments."""

    source: str
    destination: str
    protocol: Literal["tcp", "udp"] = "tcp"
    port: int = Field(ge=1, le=65535)
    reason: str = Field(min_length=1, max_length=200)


class NetworkAnswers(BaseModel):
    hub: bool = True
    egress: Literal["central", "local"] = "central"
    inspection: bool = True
    on_premises: Literal["none", "vpn", "direct_connect"] = "none"
    cidr: str = "10.0.0.0/8"
    flows: list[FlowException] = Field(default_factory=list)

    @field_validator("cidr")
    @classmethod
    def private_and_large_enough(cls, cidr: str) -> str:
        network = ipaddress.ip_network(cidr, strict=False)
        if not network.is_private:
            raise ValueError(f"{cidr} must be a private range.")
        if network.prefixlen > LARGEST_ORGANIZATION_PREFIX:
            raise ValueError(f"{cidr} is too small; use /{LARGEST_ORGANIZATION_PREFIX} or larger.")
        return str(network)


class SandboxAnswers(BaseModel):
    model: Literal["team", "developer"] = "team"
    monthly_budget_usd: int = Field(default=500, ge=1)
    expiry_days: int = Field(default=30, ge=1, le=365)


class LandingZoneAnswers(BaseModel):
    """Everything the landing zone questionnaire asks. Defaults are the platform's recommendations."""

    organization_name: str = Field(pattern=r"^[a-z][a-z0-9-]{1,30}$")
    management_email: str = Field(pattern=r"^[^@\s+]+@[^@\s]+\.[^@\s]+$")
    home_region: str
    governed_regions: list[str] = Field(min_length=2)
    environment_count: Literal[4, 5, 6] = 5
    environment_names: dict[str, str] = Field(default_factory=dict)
    grouping: Literal["separate", "prod_nonprod"] = "separate"
    account_model: Literal["environment", "portfolio", "product"] = "portfolio"
    compliance: list[ComplianceScope] = Field(default_factory=list)
    security_tooling: bool = True
    log_retention_days: int = Field(default=365, ge=1, le=3650)
    infrastructure: list[InfrastructureAccount] = Field(default_factory=lambda: list(DEFAULT_INFRASTRUCTURE))
    network: NetworkAnswers = Field(default_factory=NetworkAnswers)
    sandbox: SandboxAnswers = Field(default_factory=SandboxAnswers)
    optional_ous: list[OptionalOu] = Field(default_factory=lambda: ["exceptions", "suspended"])
    controls_profile: Literal["baseline", "recommended", "regulated"] = "recommended"

    def environments(self) -> list[EnvironmentAnswer]:
        return [environment.model_copy(update={"name": self.environment_names.get(environment.id, environment.name)})
                for environment in ENVIRONMENT_PRESETS[self.environment_count]]

    @model_validator(mode="after")
    def consistent(self) -> "LandingZoneAnswers":
        problems = [*self._region_problems(), *self._environment_problems(), *self._network_problems()]
        if problems:
            raise ValueError(" ".join(problems))
        return self

    def _region_problems(self) -> list[str]:
        problems = []
        if len(set(self.governed_regions)) != len(self.governed_regions):
            problems.append("Governed regions must be unique.")
        if self.home_region not in self.governed_regions:
            problems.append("The home region must be one of the governed regions.")
        return problems

    def _environment_problems(self) -> list[str]:
        known = {environment.id for environment in ENVIRONMENT_PRESETS[self.environment_count]}
        problems = [f"Unknown environment '{key}'." for key in self.environment_names if key not in known]
        problems += [f"Environment name '{name}' must be 2–16 letters, digits or hyphens."
                     for name in self.environment_names.values() if not _is_environment_name(name)]
        names = [environment.name.upper() for environment in self.environments()]
        if len(set(names)) != len(names):
            problems.append("Environment names must be unique.")
        return problems

    def _network_problems(self) -> list[str]:
        problems = []
        if self.network.hub and "network" not in self.infrastructure:
            problems.append("Hub-and-spoke networking needs the Network account.")
        if self.network.flows and not (self.network.hub and self.network.inspection):
            problems.append("Cross-environment flows need the hub and traffic inspection.")
        tiers = {environment.id: environment.tier for environment in self.environments()}
        for flow in self.network.flows:
            problems += _flow_problems(flow, tiers)
        return problems


def _is_environment_name(name: str) -> bool:
    import re

    return re.fullmatch(ENVIRONMENT_NAME_PATTERN, name) is not None


def _flow_problems(flow: FlowException, tiers: dict[str, str]) -> list[str]:
    if flow.source not in tiers or flow.destination not in tiers:
        return [f"Flow {flow.source} → {flow.destination} refers to an unknown environment."]
    if flow.source == flow.destination:
        return [f"Traffic inside {flow.source} is already allowed; a flow must cross environments."]
    if "sandbox" in (tiers[flow.source], tiers[flow.destination]):
        return ["Sandbox cannot have flows to other environments."]
    return []
