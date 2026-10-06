import ipaddress

from app.providers.azure.landing_zone.stacks.base import (
    LOCATION,
    ROLES_API,
    Stack,
    StackContext,
    deployment_name,
    in_resource_group,
    role_definition,
)

NETWORK_API = "2024-05-01"
DNS_API = "2024-06-01"
POLICY_API = "2023-04-01"
NETWORK_CONTRIBUTOR = "4d97b98b-1d4f-4787-a291-c67834d212e7"
HUB_GROUP = "rg-hub"
SPOKE_GROUP = "rg-network"
FIREWALL_SUBNET_PREFIX = 26
GATEWAY_SUBNET_PREFIX = 27
FIREWALL_HOST = 4  # Azure Firewall takes the fourth address of its subnet
FUNCTIONS_DELEGATION = "Microsoft.App/environments"  # Flex Consumption VNet integration (MC-4)
GATEWAYS = {"vpn": ("Vpn", "VpnGw1AZ"), "dedicated": ("ExpressRoute", "ErGw1AZ")}
# The private DNS zones of MC-4's services, and the built-in policies that add their records (MC5-9).
PRIVATE_DNS = {
    "blob": ("privatelink.blob.core.windows.net", "75973700-529f-4de2-b794-fb9b6781b6b0", {}),
    "cosmos": ("privatelink.documents.azure.com", "a63cc0bd-cda4-4178-b705-37dc439d3e0f",
               {"privateEndpointGroupId": "Sql"}),
    "servicebus": ("privatelink.servicebus.windows.net", "f0fcf93c-c063-4071-9668-c47474bd3564", {}),
    "vault": ("privatelink.vaultcore.azure.net", "ac673a9a-f77d-4846-b2d8-a57f8e1c01d4", {}),
}


def _network(type_name: str, name: str, location: str, properties: dict, **extra) -> dict:
    return {"type": f"Microsoft.Network/{type_name}", "apiVersion": NETWORK_API, "name": name, "location": location,
            **extra, "properties": properties}


def _id(type_name: str, *names: str) -> dict:
    return {"id": f"[resourceId('Microsoft.Network/{type_name}', {', '.join(repr(name) for name in names)})]"}


def _public_ip(name: str, region: str) -> dict:
    return _network("publicIPAddresses", name, region, {"publicIPAllocationMethod": "Static"}, sku={"name": "Standard"})


class NetworkStack(Stack):
    """A hub per governed region with Azure Firewall (MC5-8) in the Connectivity subscription, a spoke per workload
    subscription and region peered only to its hub (MC5-11), declared flows as firewall rules, and central private
    DNS with the policies that add its records (MC5-9)."""

    name = "lz-network"
    description = "Hubs with Azure Firewall, spokes per workload subscription, flows and private DNS"

    def resources(self, context):
        hub = context.hub_subscription()
        resources = []
        if hub:
            resources.append(in_resource_group("hub", context.subscription(hub), HUB_GROUP, LOCATION,
                                               self._hubs(context)))
            resources += self._dns_policies(context, hub)
        for account in dict.fromkeys(spoke.account for spoke in context.spokes()):
            resources += self._spoke(context, account, hub)
        return resources

    # ---- hubs ----

    def _hubs(self, context: StackContext) -> list[dict]:
        resources = []
        for region in context.regions:
            resources += self._hub(context, region)
        for zone, _, _ in PRIVATE_DNS.values():
            resources.append({"type": "Microsoft.Network/privateDnsZones", "apiVersion": DNS_API, "name": zone,
                              "location": "global", "properties": {}})
            resources += [{"type": "Microsoft.Network/privateDnsZones/virtualNetworkLinks", "apiVersion": DNS_API,
                           "name": f"{zone}/link-{region}", "location": "global", "dependsOn": [zone, f"vnet-hub-{region}"],
                           "properties": {"registrationEnabled": False,
                                          "virtualNetwork": _id("virtualNetworks", f"vnet-hub-{region}")}}
                          for region in context.regions]
        return resources

    def _hub(self, context: StackContext, region: str) -> list[dict]:
        network, answers = context.design.answers.network, context.answers
        vnet, firewall_subnet, gateway_subnet = self._hub_ranges(context, region)
        subnets = [{"name": "AzureFirewallSubnet", "properties": {"addressPrefix": firewall_subnet}}]
        gateway = GATEWAYS.get(network.on_premises)
        if gateway:
            subnets.append({"name": "GatewaySubnet", "properties": {"addressPrefix": gateway_subnet}})
        tier = answers.firewall_tier.capitalize()
        policy = {"sku": {"tier": tier}, "threatIntelMode": "Deny",
                  **({"intrusionDetection": {"mode": "Deny"}} if tier == "Premium" and network.inspection else {})}
        hub_vnet = f"vnet-hub-{region}"
        resources = [
            _network("virtualNetworks", hub_vnet, region, {"addressSpace": {"addressPrefixes": [vnet]}, "subnets": subnets}),
            _public_ip(f"pip-afw-{region}", region),
            _network("firewallPolicies", f"afwp-{region}", region, policy),
            {"type": "Microsoft.Network/firewallPolicies/ruleCollectionGroups", "apiVersion": NETWORK_API,
             "name": f"afwp-{region}/platform", "dependsOn": [f"afwp-{region}"],
             "properties": {"priority": 200, "ruleCollections": self._rule_collections(context)}},
            _network("azureFirewalls", f"afw-{region}", region, {
                "sku": {"name": "AZFW_VNet", "tier": tier}, "firewallPolicy": _id("firewallPolicies", f"afwp-{region}"),
                "ipConfigurations": [{"name": "firewall", "properties": {
                    "subnet": _id("virtualNetworks/subnets", hub_vnet, "AzureFirewallSubnet"),
                    "publicIPAddress": _id("publicIPAddresses", f"pip-afw-{region}")}}]},
                dependsOn=[hub_vnet, f"pip-afw-{region}", f"afwp-{region}/platform"])]
        if gateway:
            kind, sku = gateway
            resources += [_public_ip(f"pip-vgw-{region}", region),
                          _network("virtualNetworkGateways", f"vgw-{region}", region, {
                              "gatewayType": kind, **({"vpnType": "RouteBased"} if kind == "Vpn" else {}),
                              "sku": {"name": sku, "tier": sku}, "ipConfigurations": [{"name": "gateway", "properties": {
                                  "subnet": _id("virtualNetworks/subnets", hub_vnet, "GatewaySubnet"),
                                  "publicIPAddress": _id("publicIPAddresses", f"pip-vgw-{region}")}}]},
                              dependsOn=[hub_vnet, f"pip-vgw-{region}"])]
        return resources

    @staticmethod
    def _hub_ranges(context: StackContext, region: str) -> tuple[str, str, str]:
        vnet = ipaddress.ip_network(context.hub_address(region))
        firewall = next(vnet.subnets(new_prefix=FIREWALL_SUBNET_PREFIX))
        gateway = list(vnet.subnets(new_prefix=GATEWAY_SUBNET_PREFIX))[2]  # right after the firewall's /26
        return str(vnet), str(firewall), str(gateway)

    @staticmethod
    def _rule_collections(context: StackContext) -> list[dict]:
        def collection(name: str, priority: int, rules: list[dict]) -> dict:
            return {"ruleCollectionType": "FirewallPolicyFilterRuleCollection", "name": name, "priority": priority,
                    "action": {"type": "Allow"}, "rules": rules}

        def rule(name: str, sources: list[str], destinations: list[str], protocols: list[str], ports: list[str],
                 description: str | None = None) -> dict:
            return {"ruleType": "NetworkRule", "name": name, "sourceAddresses": sources,
                    "destinationAddresses": destinations, "ipProtocols": protocols, "destinationPorts": ports,
                    **({"description": description} if description else {})}

        ranges = {ou.key: context.environment_ranges(ou) for ou in context.environments}
        collections = [collection("within-environments", 200, [
            rule(f"within-{key.replace('_', '-')}", own, own, ["Any"], ["*"]) for key, own in ranges.items()])]
        network = context.design.answers.network
        if network.flows:
            collections.append(collection("declared-flows", 300, [
                rule(f"flow-{index}", ranges[flow.source], ranges[flow.destination], [flow.protocol.upper()],
                     [str(flow.port)], f"{flow.source} → {flow.destination} on {flow.protocol}/{flow.port}: {flow.reason}")
                for index, flow in enumerate(network.flows, start=1)]))
        if network.central_egress:
            everything = [address for own in ranges.values() for address in own]
            collections.append(collection("internet-egress", 400, [
                rule("web", everything, ["*"], ["TCP"], ["80", "443"])]))
        return collections

    def _firewall_address(self, context: StackContext, region: str) -> str:
        _, firewall, _ = self._hub_ranges(context, region)
        return str(ipaddress.ip_network(firewall)[FIREWALL_HOST])

    # ---- spokes ----

    def _spoke(self, context: StackContext, account: str, hub: str | None) -> list[dict]:
        central = hub is not None and context.design.answers.network.central_egress
        resources = []
        for spoke in [spoke for spoke in context.spokes() if spoke.account == account]:
            region = spoke.region
            functions, endpoints = spoke.subnets
            outbound, depends = {}, [f"nsg-{region}"]
            if central:
                resources.append(_network("routeTables", f"rt-{region}", region, {
                    "disableBgpRoutePropagation": True, "routes": [{"name": "default-to-firewall", "properties": {
                        "addressPrefix": "0.0.0.0/0", "nextHopType": "VirtualAppliance",
                        "nextHopIpAddress": self._firewall_address(context, region)}}]}))
                outbound, depends = {"routeTable": _id("routeTables", f"rt-{region}")}, [*depends, f"rt-{region}"]
            else:
                resources += [_public_ip(f"pip-nat-{region}", region),
                              _network("natGateways", f"nat-{region}", region, {
                                  "publicIpAddresses": [_id("publicIPAddresses", f"pip-nat-{region}")]},
                                  sku={"name": "Standard"}, dependsOn=[f"pip-nat-{region}"])]
                outbound, depends = {"natGateway": _id("natGateways", f"nat-{region}")}, [*depends, f"nat-{region}"]
            security = {"networkSecurityGroup": _id("networkSecurityGroups", f"nsg-{region}"), **outbound}
            resources += [
                _network("networkSecurityGroups", f"nsg-{region}", region, {"securityRules": []}),
                _network("virtualNetworks", f"vnet-{region}", region, {
                    "addressSpace": {"addressPrefixes": [spoke.address]}, "subnets": [
                        {"name": "functions", "properties": {"addressPrefix": functions, **security, "delegations": [
                            {"name": "flex-consumption", "properties": {"serviceName": FUNCTIONS_DELEGATION}}]}},
                        {"name": "endpoints", "properties": {"addressPrefix": endpoints, **security,
                                                             "privateEndpointNetworkPolicies": "Enabled"}}]},
                    dependsOn=depends)]
            if hub:
                resources.append(self._peering(f"vnet-{region}/to-hub", f"vnet-{region}", "hubSubscriptionId",
                                               HUB_GROUP, f"vnet-hub-{region}"))
        parameters = {"hubSubscriptionId": context.subscription(hub)} if hub else {}
        spoke = in_resource_group(deployment_name("spoke", account), context.subscription(account), SPOKE_GROUP,
                                  LOCATION, resources, parameters, ["hub"] if hub else None)
        if not hub:
            return [spoke]
        back = [self._peering(f"vnet-hub-{region}/to-{account}", None, "spokeSubscriptionId", SPOKE_GROUP,
                              f"vnet-{region}") for region in context.regions
                if any(item.account == account and item.region == region for item in context.spokes())]
        return [spoke, in_resource_group(deployment_name("hub-peers", account), context.subscription(hub), HUB_GROUP,
                                         LOCATION, back, {"spokeSubscriptionId": context.subscription(account)},
                                         [spoke["name"]])]

    @staticmethod
    def _peering(name: str, local: str | None, subscription: str, group: str, remote: str) -> dict:
        """A peering to a VNet in another subscription; the hub side's own VNet is in an earlier deployment."""
        return {"type": "Microsoft.Network/virtualNetworks/virtualNetworkPeerings", "apiVersion": NETWORK_API,
                "name": name, **({"dependsOn": [local]} if local else {}), "properties": {
                    "remoteVirtualNetwork": {"id": (f"[format('/subscriptions/{{0}}/resourceGroups/{group}/providers/"
                                                    f"Microsoft.Network/virtualNetworks/{remote}', "
                                                    f"parameters('{subscription}'))]")},
                    "allowVirtualNetworkAccess": True, "allowForwardedTraffic": True, "useRemoteGateways": False}}

    # ---- private DNS records (MC5-9) ----

    @staticmethod
    def _dns_policies(context: StackContext, hub: str) -> list[dict]:
        resources = []
        for key, (zone, definition, extra) in PRIVATE_DNS.items():
            assignment = f"ci-dns-{key}"
            zone_id = (f"[format('/subscriptions/{{0}}/resourceGroups/{HUB_GROUP}/providers/Microsoft.Network/"
                       f"privateDnsZones/{zone}', parameters('subscriptionIds')['{hub}'])]")
            resources += [
                {"type": "Microsoft.Authorization/policyAssignments", "apiVersion": POLICY_API, "name": assignment,
                 "location": LOCATION, "identity": {"type": "SystemAssigned"}, "dependsOn": ["hub"], "properties": {
                     "displayName": f"Private DNS records in {zone}",
                     "policyDefinitionId": f"/providers/Microsoft.Authorization/policyDefinitions/{definition}",
                     "parameters": {"privateDnsZoneId": {"value": zone_id}, "effect": {"value": "DeployIfNotExists"},
                                    **{name: {"value": value} for name, value in extra.items()}}}},
                {"type": "Microsoft.Authorization/roleAssignments", "apiVersion": ROLES_API,
                 "name": f"[guid('{context.organization}', 'dns', '{key}')]", "dependsOn": [assignment], "properties": {
                     "roleDefinitionId": role_definition(NETWORK_CONTRIBUTOR), "principalType": "ServicePrincipal",
                     "principalId": (f"[reference(extensionResourceId(managementGroup().id, "
                                     f"'Microsoft.Authorization/policyAssignments', '{assignment}'), '{POLICY_API}', "
                                     "'full').identity.principalId]")}}]
        return resources
