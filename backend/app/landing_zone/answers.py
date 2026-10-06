import ipaddress
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.landing_zone.catalog.packs import PackRegistry

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


# The environments a design can include, in pipeline order. STAGE and PROD are always included (§20.12.4).
ENVIRONMENT_CATALOG: dict[str, EnvironmentAnswer] = {environment.id: environment for environment in [
    EnvironmentAnswer(id="sandbox", name="Sandbox", tier="sandbox"),
    EnvironmentAnswer(id="dev", name="DEV", tier="nonprod"),
    EnvironmentAnswer(id="qa", name="QA", tier="nonprod"),
    EnvironmentAnswer(id="test", name="TEST", tier="nonprod"),
    EnvironmentAnswer(id="uat", name="UAT", tier="nonprod"),
    EnvironmentAnswer(id="perf", name="PERF", tier="nonprod"),
    EnvironmentAnswer(id="stage", name="STAGE", tier="prod"),
    EnvironmentAnswer(id="prod", name="PROD", tier="prod"),
]}
REQUIRED_ENVIRONMENTS = ("stage", "prod")
ENVIRONMENT_PRESETS: dict[int, list[str]] = {
    4: ["sandbox", "dev", "stage", "prod"],
    5: ["sandbox", "dev", "test", "stage", "prod"],
    6: ["sandbox", "dev", "test", "uat", "stage", "prod"],
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
    on_premises: Literal["none", "vpn", "dedicated"] = "none"  # dedicated: Direct Connect, Cloud Interconnect
    cidr: str = "10.0.0.0/8"
    flows: list[FlowException] = Field(default_factory=list)

    @field_validator("on_premises", mode="before")
    @classmethod
    def dedicated_link(cls, value):
        """Designs saved before §22.10 named the dedicated link after AWS Direct Connect."""
        return "dedicated" if value == "direct_connect" else value

    @property
    def central_egress(self) -> bool:
        return self.hub and self.egress == "central"

    @property
    def inspects_flows(self) -> bool:
        """The firewall sits in the central egress VPC, so inspection needs the hub and central egress."""
        return self.central_egress and self.inspection

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


class TemplateReference(BaseModel):
    """The industry template, and its version, that a design started from."""

    id: str
    version: int


class LandingZoneAnswers(BaseModel):
    """Everything the landing zone questionnaire asks. Defaults are the platform's recommendations. What only one
    cloud asks (an AWS management email, a Google Cloud billing account) is in `provider_answers`, which that
    cloud's landing-zone toolkit validates (§22.10.3)."""

    organization_name: str = Field(pattern=r"^[a-z][a-z0-9-]{1,30}$")
    provider_answers: dict = Field(default_factory=dict)
    home_region: str
    governed_regions: list[str] = Field(min_length=2)
    template: TemplateReference | None = None
    environment_ids: list[str] = Field(default_factory=lambda: list(ENVIRONMENT_PRESETS[5]))
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
    control_packs: list[str] | None = None
    pack_parameters: dict[str, dict[str, list[str]]] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def legacy_provider_answer(cls, data):
        """Designs saved before §22.10 kept the AWS management email among the neutral answers."""
        if not isinstance(data, dict) or "management_email" not in data:
            return data
        upgraded = dict(data)
        email = upgraded.pop("management_email")
        upgraded["provider_answers"] = {"management_email": email, **upgraded.get("provider_answers", {})}
        return upgraded

    @model_validator(mode="before")
    @classmethod
    def legacy_environment_count(cls, data):
        """Designs saved before §20.12 chose 4, 5 or 6 environments; map the count to its preset."""
        if "environment_count" not in data:
            return data
        upgraded = dict(data)
        count = upgraded.pop("environment_count")
        if count not in ENVIRONMENT_PRESETS:
            raise ValueError(f"Choose 4, 5 or 6 environments, not {count}.")
        upgraded.setdefault("environment_ids", list(ENVIRONMENT_PRESETS[count]))
        return upgraded

    def environments(self) -> list[EnvironmentAnswer]:
        chosen = set(self.environment_ids)
        return [environment.model_copy(update={"name": self.environment_names.get(environment.id, environment.name)})
                for environment in ENVIRONMENT_CATALOG.values() if environment.id in chosen]

    def packs(self) -> list[str]:
        """The control packs to apply: the explicit choice, else the controls profile's packs."""
        return self.control_packs if self.control_packs is not None else PackRegistry.default().for_profile(
            self.controls_profile)

    @model_validator(mode="after")
    def consistent(self) -> "LandingZoneAnswers":
        problems = [*self._region_problems(), *self._environment_set_problems(), *self._environment_problems(),
                    *self._network_problems(), *self._pack_problems()]
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

    def _environment_set_problems(self) -> list[str]:
        problems = [f"Unknown environment '{key}'." for key in self.environment_ids if key not in ENVIRONMENT_CATALOG]
        if len(set(self.environment_ids)) != len(self.environment_ids):
            problems.append("Each environment can be chosen once.")
        if not set(REQUIRED_ENVIRONMENTS) <= set(self.environment_ids):
            problems.append("STAGE and PROD are always included.")
        if not any(environment.tier == "nonprod" for environment in self.environments()):
            problems.append("Choose at least one non-production environment.")
        return problems

    def _pack_problems(self) -> list[str]:
        known = PackRegistry.default()
        problems = [f"Unknown control pack '{pack}'." for pack in self.control_packs or [] if not known.knows(pack)]
        return problems + [f"Parameters for control pack '{pack}', which is not chosen." for pack in self.pack_parameters
                           if pack not in self.packs()]

    def _environment_problems(self) -> list[str]:
        known = set(self.environment_ids)
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
        if self.network.flows and not self.network.inspects_flows:
            problems.append("Cross-environment flows need the hub, central egress and traffic inspection.")
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
