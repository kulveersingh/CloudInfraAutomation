"""Local stand-in for applying the Azure landing zone's deployment stacks (§22.12.6)."""

import json
import uuid
from pathlib import Path

from app.config import Settings
from app.landing_zone.design import LandingZoneDesign, OrgCatalog
from app.landing_zone.executor import LandingZoneExecutor, LandingZoneOutputs, NetworkOutput
from app.providers.azure.landing_zone.bundle import STACKS
from app.providers.azure.landing_zone.stacks.base import Spoke, StackContext
from app.providers.azure.landing_zone.stacks.network import SPOKE_GROUP

HISTORY_FILE = "landing-zone-runs.json"


class LocalAzureLandingZone(LandingZoneExecutor):
    """Azure assigns subscription ids when aliases are created; the stand-in gives each a stable GUID from the
    tenant and alias name. Each spoke (a workload subscription in a region) is reported as that subscription's
    network, with its functions and endpoints subnets, as MC-4 projects expect."""

    def __init__(self, root):
        self._history_file = Path(root) / "azure" / HISTORY_FILE

    @classmethod
    def from_settings(cls, settings: Settings) -> "LocalAzureLandingZone":
        return cls(settings.local_state_dir)

    def apply(self, design: LandingZoneDesign) -> LandingZoneOutputs:
        context = StackContext(design, OrgCatalog(portfolios=[], products=[]))
        accounts = {account.name: str(uuid.uuid5(uuid.NAMESPACE_URL,
                                                  f"cloudinfra:azure:{context.answers.tenant_id}:{account.name}"))
                    for account in design.accounts()}
        labels = {ou.key: ou.name for ou in context.environments}
        networks = [self._network(spoke, accounts[spoke.account], labels[spoke.environment])
                    for spoke in context.spokes()]
        self._record({"organization": context.organization, "stacks": [stack.name for stack in STACKS],
                      "subscriptions": len(accounts)})
        return LandingZoneOutputs(accounts=accounts, networks=networks,
                                  vault_account=context.unit("backup") if context.vends("backup") else None)

    def history(self) -> list[dict]:
        if not self._history_file.exists():
            return []
        return json.loads(self._history_file.read_text())

    @staticmethod
    def _network(spoke: Spoke, subscription: str, label: str) -> NetworkOutput:
        providers = f"/subscriptions/{subscription}/resourceGroups/{SPOKE_GROUP}/providers/Microsoft.Network"
        vnet = f"{providers}/virtualNetworks/vnet-{spoke.region}"
        return NetworkOutput(environment=spoke.environment, region=spoke.region, network_ref=vnet, cidr=spoke.address,
                             subnet_refs=[f"{vnet}/subnets/functions", f"{vnet}/subnets/endpoints"],
                             firewall_ref=f"{providers}/networkSecurityGroups/nsg-{spoke.region}",
                             account_names=[spoke.account], label=label)

    def _record(self, entry: dict) -> None:
        self._history_file.parent.mkdir(parents=True, exist_ok=True)
        self._history_file.write_text(json.dumps([*self.history(), entry], indent=2))
