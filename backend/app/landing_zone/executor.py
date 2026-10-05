from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from app.landing_zone.design import LandingZoneDesign


@dataclass(frozen=True)
class NetworkOutput:
    environment: str
    region: str
    vpc_id: str
    cidr: str
    subnet_ids: list[str]
    security_group_id: str
    account_names: list[str]
    label: str


@dataclass(frozen=True)
class LandingZoneOutputs:
    accounts: dict[str, str]
    networks: list[NetworkOutput] = field(default_factory=list)


class LandingZoneExecutor(ABC):
    """Applies an approved landing zone and reports account ids and shared VPCs (from the stack outputs)."""

    @abstractmethod
    def apply(self, design: LandingZoneDesign) -> LandingZoneOutputs:
        ...
