import json
from pathlib import Path

from app.config import Settings
from app.landing_zone.design import LandingZoneDesign, OrgCatalog
from app.landing_zone.executor import LandingZoneExecutor, LandingZoneOutputs, NetworkOutput
from app.providers.gcp.landing_zone.bundle import DEPLOYMENTS
from app.providers.gcp.landing_zone.deployments.base import DeploymentContext, Environment, resource_name

HISTORY_FILE = "landing-zone-runs.json"


class LocalGcpLandingZone(LandingZoneExecutor):
    """Local stand-in for applying the Infrastructure Manager deployments: project ids are the vended projects'
    ids (they are chosen, not assigned), and each environment reports its Shared VPC subnet per region."""

    def __init__(self, root):
        self._history_file = Path(root) / "gcp" / HISTORY_FILE

    @classmethod
    def from_settings(cls, settings: Settings) -> "LocalGcpLandingZone":
        return cls(settings.local_state_dir)

    def apply(self, design: LandingZoneDesign) -> LandingZoneOutputs:
        context = DeploymentContext(design, OrgCatalog(portfolios=[], products=[]))
        accounts = {account.name: account.name for account in design.accounts()}
        networks = [self._network(context, environment, region)
                    for environment in context.environments for region in context.regions]
        self._record({"organization": design.answers.organization_name,
                      "deployments": [deployment.name for deployment in DEPLOYMENTS], "projects": len(accounts)})
        return LandingZoneOutputs(accounts=accounts, networks=networks, vault_account=context.unit("backup"))

    def history(self) -> list[dict]:
        if not self._history_file.exists():
            return []
        return json.loads(self._history_file.read_text())

    def _network(self, context: DeploymentContext, environment: Environment, region: str) -> NetworkOutput:
        key, host = environment.ou.key, environment.host.name
        return NetworkOutput(environment=key, region=region,
                             network_ref=f"projects/{host}/global/networks/vpc-{resource_name(key)}",
                             cidr=context.subnet(key, region),
                             subnet_refs=[f"projects/{host}/regions/{region}/subnetworks/{resource_name(key)}-{region}"],
                             firewall_ref=f"{context.design.answers.organization_name}-{resource_name(key)}",
                             account_names=[workload.name for workload in environment.workloads],
                             label=environment.ou.name)

    def _record(self, entry: dict) -> None:
        self._history_file.parent.mkdir(parents=True, exist_ok=True)
        self._history_file.write_text(json.dumps([*self.history(), entry], indent=2))
