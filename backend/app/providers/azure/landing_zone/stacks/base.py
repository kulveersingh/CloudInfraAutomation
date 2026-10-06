import hashlib
import ipaddress
import math
from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.landing_zone.catalog.packs import PackRegistry
from app.landing_zone.catalog.resolver import EnabledControl, PackResolver
from app.landing_zone.design import AccountPlan, LandingZoneDesign, OrgCatalog, OuNode
from app.landing_zone.ipam import IpamPlanner
from app.providers.azure.landing_zone.answers import AzureLandingZoneAnswers, azure_answers
from app.providers.azure.landing_zone.controls import azure_controls
from app.providers.azure.landing_zone.limits import management_group_id

MANAGEMENT_GROUP_SCHEMA = ("https://schema.management.azure.com/schemas/2019-08-01/"
                           "managementGroupDeploymentTemplate.json#")
SUBSCRIPTION_SCHEMA = "https://schema.management.azure.com/schemas/2018-05-01/subscriptionDeploymentTemplate.json#"
TENANT_SCHEMA = "https://schema.management.azure.com/schemas/2019-08-01/tenantDeploymentTemplate.json#"
RESOURCE_GROUP_SCHEMA = "https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#"
PARAMETERS_SCHEMA = "https://schema.management.azure.com/schemas/2019-04-01/deploymentParameters.json#"
DEPLOYMENTS_API = "2024-03-01"
RESOURCE_GROUPS_API = "2024-03-01"
ROLES_API = "2022-04-01"
STRING = {"type": "string"}
LOCATION = "[parameters('location')]"
HUB_SLOT = "hub"
MAX_DEPLOYMENT_NAME = 64
PARAMETER_TYPES = {str: "string", list: "array", dict: "object", int: "int", bool: "bool"}


def management_group_resource_id(name: str) -> str:
    return f"/providers/Microsoft.Management/managementGroups/{name}"


def role_definition(role: str) -> str:
    return f"/providers/Microsoft.Authorization/roleDefinitions/{role}"


def deployment_name(*parts: str) -> str:
    """Deployment names are at most 64 characters; a long one keeps a hash of the whole name."""
    name = "-".join(parts)
    if len(name) <= MAX_DEPLOYMENT_NAME:
        return name
    return f"{name[:MAX_DEPLOYMENT_NAME - 9]}-{hashlib.sha1(name.encode()).hexdigest()[:8]}"


def escaped(value):
    """Policy rules are evaluated by Azure Policy, not by ARM, so their expressions are escaped in a template."""
    if isinstance(value, str):
        return f"[{value}" if value.startswith("[") else value
    if isinstance(value, list):
        return [escaped(item) for item in value]
    if isinstance(value, dict):
        return {key: escaped(item) for key, item in value.items()}
    return value


def template(schema: str, resources: list[dict], parameters: dict[str, object] | None = None) -> dict:
    declared = {name: {"type": PARAMETER_TYPES[type(value)]} for name, value in (parameters or {}).items()}
    return {"$schema": schema, "contentVersion": "1.0.0.0", "parameters": declared, "resources": resources}


def nested(name: str, schema: str, resources: list[dict], parameters: dict[str, object] | None = None,
           depends: list[str] | None = None, **target) -> dict:
    """A deployment into another scope (`scope`, `subscriptionId`, `resourceGroup`); its template evaluates its own
    expressions, so what it needs from outside is passed as parameters."""
    body = {"type": "Microsoft.Resources/deployments", "apiVersion": DEPLOYMENTS_API, "name": name, **target}
    if "resourceGroup" not in target:
        body["location"] = LOCATION
    body["properties"] = {"mode": "Incremental", "expressionEvaluationOptions": {"scope": "inner"},
                          "parameters": {key: {"value": value} for key, value in (parameters or {}).items()},
                          "template": template(schema, resources, parameters)}
    return {**body, **({"dependsOn": depends} if depends else {})}


def in_resource_group(name: str, subscription: str, group: str, location: str, resources: list[dict],
                      parameters: dict[str, object] | None = None, depends: list[str] | None = None) -> dict:
    """A management-group template reaches a resource group through its subscription: the subscription-scope
    deployment creates the group, then deploys into it."""
    inner = {"location": location, **(parameters or {})}
    group_resource = {"type": "Microsoft.Resources/resourceGroups", "apiVersion": RESOURCE_GROUPS_API, "name": group,
                      "location": "[parameters('location')]"}
    passed = {key: f"[parameters('{key}')]" for key in (parameters or {})}
    deploy = nested(f"{name}-rg", RESOURCE_GROUP_SCHEMA, resources, passed, [group], resourceGroup=group)
    return nested(name, SUBSCRIPTION_SCHEMA, [group_resource, deploy], inner, depends, subscriptionId=subscription)


@dataclass(frozen=True)
class Spoke:
    """A workload subscription's VNet in one region, with its function and endpoint subnets."""

    account: str
    environment: str
    region: str
    address: str

    @property
    def subnets(self) -> tuple[str, str]:
        functions, endpoints = ipaddress.ip_network(self.address).subnets(prefixlen_diff=1)
        return str(functions), str(endpoints)


class StackContext:
    """What every stack reads: the design, Azure's answers, resolved controls, subscriptions and the address plan."""

    def __init__(self, design: LandingZoneDesign, catalog: OrgCatalog):
        self.design = design
        self.catalog = catalog
        self.answers: AzureLandingZoneAnswers = azure_answers(design.answers)
        self.organization = design.answers.organization_name
        self.controls: dict[str, list[EnabledControl]] = PackResolver(
            PackRegistry.default(), azure_controls()).resolve(design).controls
        self._parents = {child.key: parent for parent in design.walk() for child in parent.children}
        self.environments = [ou for ou in design.environment_ous() if ou.tier != "sandbox"]
        slots = [ou.key for ou in self.environments] + [HUB_SLOT]
        self._plan = IpamPlanner().plan(design.answers.network.cidr, list(design.answers.governed_regions), slots)

    @property
    def regions(self) -> list[str]:
        return list(self.design.answers.governed_regions)

    @property
    def home(self) -> str:
        return self.design.answers.home_region

    def management_group(self, ou: OuNode | None) -> str:
        return self.organization if ou is None else management_group_id(self.organization, ou)

    def parent(self, ou: OuNode) -> OuNode | None:
        return self._parents.get(ou.key)

    def node_of(self, account: AccountPlan) -> OuNode:
        return next(ou for ou in self.design.walk() if account in ou.accounts)

    def tier_of(self, ou: OuNode | None) -> str | None:
        while ou is not None and ou.tier is None:
            ou = self.parent(ou)
        return None if ou is None else ou.tier

    def unit(self, key: str) -> str:
        """A shared subscription by its Infrastructure answer (network, backup, ...)."""
        return self.design.namer.unit(self.design.units.infrastructure[key]).name

    def vends(self, key: str) -> bool:
        """Whether the design has the shared subscription of an Infrastructure answer."""
        return key in self.design.answers.infrastructure

    def hub_subscription(self) -> str | None:
        """The Connectivity subscription that holds the hubs, when the design has a hub."""
        return self.unit("network") if self.design.answers.network.hub and self.vends("network") else None

    def security_unit(self, index: int) -> str:
        return self.design.namer.unit(self.design.units.security[index]).name

    @staticmethod
    def subscription(name: str) -> str:
        """A vended subscription's id, resolved by the workflow after lz-subscriptions."""
        return f"[parameters('subscriptionIds')['{name}']]"

    def accounts(self) -> list[AccountPlan]:
        return self.design.accounts()

    def sandbox_accounts(self) -> list[AccountPlan]:
        return [account for ou in self.design.environment_ous() if ou.tier == "sandbox"
                for account in ou.enabled_accounts()]

    def environment_ranges(self, ou: OuNode) -> list[str]:
        return [self._plan.pool(region, ou.key) for region in self.regions]

    def hub_address(self, region: str) -> str:
        pool = ipaddress.ip_network(self._plan.pool(region, HUB_SLOT))
        return str(next(pool.subnets(new_prefix=max(22, pool.prefixlen))))

    def spokes(self) -> list[Spoke]:
        spokes = []
        for ou in self.environments:
            workloads = [account.name for account in ou.subtree_accounts() if account.enabled]
            for region in self.regions:
                pool = ipaddress.ip_network(self._plan.pool(region, ou.key))
                prefix = pool.prefixlen + math.ceil(math.log2(max(len(workloads), 1)))
                spokes += [Spoke(name, ou.key, region, str(address))
                           for name, address in zip(workloads, pool.subnets(new_prefix=prefix), strict=False)]
        return spokes


class Stack(ABC):
    """One deployment stack of the landing zone, applied in order at the organization's management group."""

    name: str
    description: str
    unmanaged: str = "deleteResources"  # what removing a resource from the template does (MC5-5)
    needs_subscription_ids: bool = True  # every stack after lz-subscriptions

    def render(self, context: StackContext) -> dict:
        parameters = {"location": STRING, **({"subscriptionIds": {"type": "object"}}
                                             if self.needs_subscription_ids else {})}
        resources = self.resources(context)
        return {"$schema": MANAGEMENT_GROUP_SCHEMA, "contentVersion": "1.0.0.0",
                "metadata": {"_generator": {"name": "cloudinfra"}}, "parameters": parameters, "resources": resources}

    def parameters(self, context: StackContext) -> dict:
        return {"$schema": PARAMETERS_SCHEMA, "contentVersion": "1.0.0.0",
                "parameters": {"location": {"value": context.home}}}

    @abstractmethod
    def resources(self, context: StackContext) -> list[dict]:
        ...
