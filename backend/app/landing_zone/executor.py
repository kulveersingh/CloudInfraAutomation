from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from app.landing_zone.design import LandingZoneDesign


@dataclass(frozen=True)
class NetworkOutput:
    environment: str
    region: str
    network_ref: str
    cidr: str
    subnet_refs: list[str]
    firewall_ref: str
    account_names: list[str]
    label: str


@dataclass(frozen=True)
class LandingZoneOutputs:
    accounts: dict[str, str]
    networks: list[NetworkOutput] = field(default_factory=list)
    vault_account: str | None = None  # the unit holding the locked teardown vault


class LandingZoneExecutor(ABC):
    """Applies an approved landing zone and reports account ids and shared VPCs (from the stack outputs)."""

    @abstractmethod
    def apply(self, design: LandingZoneDesign) -> LandingZoneOutputs:
        ...
