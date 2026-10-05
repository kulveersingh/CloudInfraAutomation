import hashlib
import json
from pathlib import Path

from app.config import Settings
from app.landing_zone.design import LandingZoneDesign
from app.landing_zone.executor import LandingZoneExecutor, LandingZoneOutputs, NetworkOutput
from app.providers.aws.landing_zone.cloudformation.bundle import STACK_FILES
from app.providers.aws.landing_zone.cloudformation.network import NetworkLayout

HISTORY_FILE = "landing-zone-runs.json"
ACCOUNT_ID_SPACE = 10 ** 12


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

        return NetworkOutput(environment=ou.key, region=region, network_ref=resource_id("vpc", "vpc"),
                             cidr=layout.vpc_cidr(region, ou.key),
                             subnet_refs=[resource_id("subnet", "a"), resource_id("subnet", "b")],
                             firewall_ref=resource_id("sg", "org"),
                             account_names=[account.name for account in ou.subtree_accounts() if account.enabled],
                             label=ou.name)

    def _record(self, entry: dict) -> None:
        self._history_file.parent.mkdir(parents=True, exist_ok=True)
        self._history_file.write_text(json.dumps([*self.history(), entry], indent=2))

    @staticmethod
    def _digest(*parts: str) -> str:
        return hashlib.sha256(":".join(parts).encode()).hexdigest()
