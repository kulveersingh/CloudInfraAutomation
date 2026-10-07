import ipaddress
from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.landing_zone.catalog.packs import PackRegistry
from app.landing_zone.catalog.resolver import EnabledControl, PackResolver
from app.landing_zone.design import AccountPlan, LandingZoneDesign, OrgCatalog, OuNode
from app.landing_zone.ipam import IpamPlanner
from app.providers.gcp.landing_zone.answers import GcpLandingZoneAnswers, gcp_answers
from app.providers.gcp.landing_zone.controls import gcp_controls
from app.providers.gcp.project.document import TerraformDocument

STRING = {"type": "string"}
INPUTS = {"organization_id": STRING, "billing_account": STRING, "seed_project": STRING, "region": STRING}
ORGANIZATION_PROVIDER = {"billing_project": "${var.seed_project}", "user_project_override": True,
                         "region": "${var.region}"}
ORGANIZATION = "organizations/${var.organization_id}"
HUB_SLOT = "hub"
SUBNET_PREFIX = 20
SECONDS_IN_A_DAY = 86400
TEARDOWN_RETENTION_DAYS = 60


def group(email: str) -> str:
    return f"principalSet://goog/group/{email}"


def resource_name(key: str) -> str:
    """A name Google Cloud accepts for policies and perimeters: lowercase letters, digits and hyphens."""
    return key.replace("_", "-").lower()


@dataclass(frozen=True)
class Environment:
    """A workload environment's isolation domain: its folder, Shared VPC host project and workload projects."""

    ou: OuNode
    host: AccountPlan
    workloads: list[AccountPlan]


class DeploymentContext:
    """What every deployment reads: the design, the cloud's answers, resolved controls and the address plan."""

    def __init__(self, design: LandingZoneDesign, catalog: OrgCatalog):
        self.design = design
        self.catalog = catalog
        self.answers: GcpLandingZoneAnswers = gcp_answers(design.answers)
        self.controls: dict[str, list[EnabledControl]] = PackResolver(PackRegistry.default(), gcp_controls()).resolve(
            design).controls
        self.environments = self._environments()
        slots = [environment.ou.key for environment in self.environments] + [HUB_SLOT]
        self._plan = IpamPlanner().plan(design.answers.network.cidr, design.answers.governed_regions, slots)

    @property
    def regions(self) -> list[str]:
        return list(self.design.answers.governed_regions)

    def project_id(self, suffix: str) -> str:
        return self.design.namer.unit(suffix).name

    def vends(self, key: str) -> bool:
        """Whether the design has the shared project of an Infrastructure answer."""
        return key in self.design.answers.infrastructure

    def unit(self, key: str) -> str:
        """A shared project by its Infrastructure answer (network, backup, ...)."""
        return self.project_id(self.design.units.infrastructure[key])

    @property
    def security_projects(self) -> tuple[str, str]:
        logging, security = self.design.units.security
        return self.project_id(logging), self.project_id(security)

    def subnet(self, slot: str, region: str) -> str:
        pool = ipaddress.ip_network(self._plan.pool(region, slot))
        return str(next(pool.subnets(new_prefix=max(SUBNET_PREFIX, pool.prefixlen))))

    def placed(self, implementations: set[str]) -> list[tuple[OuNode, EnabledControl]]:
        return [(ou, enabled) for ou in self.design.walk() for enabled in self.controls.get(ou.key, [])
                if enabled.control.implementation in implementations]

    def _environments(self) -> list[Environment]:
        environments = []
        for ou in self.design.environment_ous():
            suffix = self.design.units.host_for(ou.name)
            if ou.tier == "sandbox" or suffix is None:
                continue
            host = self.project_id(suffix)
            workloads = [account for account in self.design.accounts()
                         if account.domain == ou.key and account.name != host]
            environments.append(Environment(ou, next(account for account in ou.accounts if account.name == host),
                                            workloads))
        return environments


class FolderReferences:
    """Folders by Terraform expression: the resources in lz-structure, data sources (found by name under their
    parent) in every later deployment, since Infrastructure Manager deployments don't share state."""

    def __init__(self, design: LandingZoneDesign, owned: bool):
        self._parents = {child.key: parent for parent in design.walk() for child in parent.children}
        self._owned = owned
        self._design = design

    def name(self, ou: OuNode) -> str:
        source = "google_folder" if self._owned else "data.google_active_folder"
        return f"${{{source}.{ou.key}.name}}"

    def parent(self, ou: OuNode) -> str:
        parent = self._parents.get(ou.key)
        return ORGANIZATION if parent is None else self.name(parent)

    def add_lookups(self, document: TerraformDocument) -> None:
        for ou in self._design.walk():
            document.add_data("google_active_folder", ou.key, {"display_name": ou.name, "parent": self.parent(ou)})


class Deployment(ABC):
    """One Infrastructure Manager deployment of the landing zone, applied in order from the seed project."""

    name: str
    description: str

    def render(self, context: DeploymentContext) -> dict:
        document = TerraformDocument(ORGANIZATION_PROVIDER)
        for variable, body in INPUTS.items():
            document.add_variable(variable, body)
        self.build(context, document)
        return document.to_dict()

    @abstractmethod
    def build(self, context: DeploymentContext, document: TerraformDocument) -> None:
        ...
