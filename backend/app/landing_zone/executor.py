import hashlib
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

from app.config import Settings
from app.landing_zone.cloudformation.bundle import STACK_FILES
from app.landing_zone.cloudformation.network import NetworkLayout
from app.landing_zone.design import LandingZoneDesign

HISTORY_FILE = "landing-zone-runs.json"
ACCOUNT_ID_SPACE = 10 ** 12


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


class LocalLandingZoneExecutor(LandingZoneExecutor):
    """Local stand-in: derives stable ids instead of calling AWS, and records each run."""

    def __init__(self, root):
        self._history_file = Path(root) / "aws" / HISTORY_FILE

    @classmethod
    def from_settings(cls, settings: Settings) -> "LocalLandingZoneExecutor":
        return cls(settings.local_state_dir)

    def apply(self, design: LandingZoneDesign) -> LandingZoneOutputs:
        organization = design.answers.organization_name
        accounts = {account.name: f"{int(self._digest(organization, account.name), 16) % ACCOUNT_ID_SPACE:012d}"
                    for account in design.accounts()}
        layout = NetworkLayout(design)
        networks = [self._network(organization, layout, ou, region)
                    for ou in layout.environments for region in layout.regions]
        self._record({"organization": organization, "stacks": list(STACK_FILES), "accounts": len(accounts)})
        return LandingZoneOutputs(accounts=accounts, networks=networks)

    def history(self) -> list[dict]:
        if not self._history_file.exists():
            return []
        return json.loads(self._history_file.read_text())

    def _network(self, organization: str, layout: NetworkLayout, ou, region: str) -> NetworkOutput:
        def resource_id(prefix: str, suffix: str) -> str:
            return f"{prefix}-{self._digest(organization, ou.key, region, suffix)[:17]}"

        return NetworkOutput(environment=ou.key, region=region, vpc_id=resource_id("vpc", "vpc"),
                             cidr=layout.vpc_cidr(region, ou.key),
                             subnet_ids=[resource_id("subnet", "a"), resource_id("subnet", "b")],
                             security_group_id=resource_id("sg", "org"),
                             account_names=[account.name for account in ou.accounts], label=ou.name)

    def _record(self, entry: dict) -> None:
        self._history_file.parent.mkdir(parents=True, exist_ok=True)
        self._history_file.write_text(json.dumps([*self.history(), entry], indent=2))

    @staticmethod
    def _digest(*parts: str) -> str:
        return hashlib.sha256(":".join(parts).encode()).hexdigest()
