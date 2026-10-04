import ipaddress

from app.landing_zone.cloudformation.base import StackContext, StackRenderer
from app.landing_zone.cloudformation.references import pascal
from app.landing_zone.design import LandingZoneDesign
from app.landing_zone.ipam import IpamPlanner

VPC_PREFIX = 16
SHARED_SLOT = "shared"
ANYWHERE = "0.0.0.0/0"
OU_ARN_PATTERN = r"^arn:aws:organizations::\d{12}:ou/o-[a-z0-9]{10,32}/ou-[0-9a-z]{4,32}-[a-z0-9]{8,32}$"
FIREWALL_ENDPOINT = {"Fn::Select": [1, {"Fn::Split": [":", {"Fn::Select": [0, {"Fn::GetAtt": ["Firewall", "EndpointIds"]}]}]}]}


def _az(index: int) -> dict:
    return {"Fn::Select": [index, {"Fn::GetAZs": {"Ref": "AWS::Region"}}]}


def _subnet_cidr(vpc: str, index: int, count: int, bits: int) -> dict:
    return {"Fn::Select": [index, {"Fn::Cidr": [{"Fn::GetAtt": [vpc, "CidrBlock"]}, count, bits]}]}


def _tags(name: str) -> list[dict]:
    return [{"Key": "Name", "Value": name}]


class NetworkLayout:
    """Address plan for the shared VPCs: one per environment OU plus Shared Services and Egress, per region."""

    def __init__(self, design: LandingZoneDesign):
        answers = design.answers
        self.environments = design.environment_ous()
        slots = [ou.key for ou in self.environments] + [SHARED_SLOT]
        self._plan = IpamPlanner().plan(answers.network.cidr, answers.governed_regions, slots)
        self.regions = answers.governed_regions

    def mapping(self) -> dict:
        return {region: {**{pascal(ou.key): self.vpc_cidr(region, ou.key) for ou in self.environments},
                         **dict(zip(("Egress", "SharedServices"), self._shared(region), strict=True))}
                for region in self.regions}

    def vpc_cidr(self, region: str, slot: str) -> str:
        pool = ipaddress.ip_network(self._plan.pool(region, slot))
        return str(next(pool.subnets(new_prefix=max(VPC_PREFIX, pool.prefixlen))))

    def environment_cidrs(self, key: str) -> list[str]:
        return [self.vpc_cidr(region, key) for region in self.regions]

    def _shared(self, region: str) -> list[str]:
        pool = ipaddress.ip_network(self._plan.pool(region, SHARED_SLOT))
        return [str(block) for block in list(pool.subnets(new_prefix=max(VPC_PREFIX, pool.prefixlen + 1)))[:2]]


class FirewallRules:
    """Suricata rules: web egress, each declared flow as a single port, everything else internal is dropped."""

    def __init__(self, context: StackContext, layout: NetworkLayout):
        self._flows = context.design.answers.network.flows
        self._layout = layout

    def text(self) -> str:
        rules = ['pass tcp $HOME_NET any -> !$HOME_NET [80,443] (msg:"internet web egress"; sid:100; rev:1;)',
                 'pass udp $HOME_NET any -> !$HOME_NET 123 (msg:"time sync"; sid:101; rev:1;)']
        for index, flow in enumerate(self._flows):
            source, destination = (self._cidrs(flow.source), self._cidrs(flow.destination))
            reason = "".join(character for character in flow.reason if character not in '";\\')
            rules.append(f'pass {flow.protocol} {source} any -> {destination} {flow.port} '
                         f'(msg:"{flow.source} to {flow.destination}: {reason}"; sid:{1000001 + index}; rev:1;)')
        rules += ['drop ip $HOME_NET any -> $HOME_NET any (msg:"undeclared cross-environment traffic"; sid:999998; rev:1;)',
                  'drop ip $HOME_NET any -> !$HOME_NET any (msg:"other internet traffic"; sid:999999; rev:1;)']
        return "\n".join(rules) + "\n"

    def _cidrs(self, environment: str) -> str:
        return "[" + ",".join(self._layout.environment_cidrs(environment)) + "]"


class NetworkStack(StackRenderer):
    """Shared VPCs owned by the Network account, one Transit Gateway route domain per environment, central egress
    with AWS Network Firewall. Deployed once per governed region."""

    name = "lz-network"
    description = ("Landing zone network: shared VPC per environment (subnets shared to its OU with RAM), "
                   "Transit Gateway route table per environment, central egress and inspection.")

    def sections(self, context: StackContext) -> dict:
        builder = _NetworkBuilder(context, NetworkLayout(context.design))
        return builder.build()


class _NetworkBuilder:
    def __init__(self, context: StackContext, layout: NetworkLayout):
        network = context.design.answers.network
        self._context = context
        self._layout = layout
        self._organization = context.design.answers.organization_name
        self._hub = network.hub
        self._central = network.central_egress
        self._inspection = network.inspects_flows
        self._cidr = network.cidr
        self._resources: dict = {}
        self._outputs: dict = {}

    def build(self) -> dict:
        infrastructure = next(ou for ou in self._context.design.walk() if ou.kind == "infrastructure")
        if self._hub:
            self._transit_gateway()
        for ou in self._layout.environments:
            self._shared_vpc(pascal(ou.key), ou.name, f"Ou{pascal(ou.key)}Arn")
        self._shared_vpc("SharedServices", "Shared Services", f"Ou{pascal(infrastructure.key)}Arn")
        if self._hub:
            self._routing()
        if self._central:
            self._egress_vpc()
        parameters = {f"Ou{pascal(ou.key)}Arn": {"Type": "String", "AllowedPattern": OU_ARN_PATTERN}
                      for ou in [*self._layout.environments, infrastructure]}
        return {"Parameters": parameters, "Mappings": {"Cidrs": self._layout.mapping()},
                "Resources": self._resources, "Outputs": self._outputs}

    def _add(self, key: str, type_name: str, properties: dict, depends: list[str] | None = None) -> None:
        body = {"Type": type_name, "Properties": properties}
        self._resources[key] = {**body, "DependsOn": depends} if depends else body

    # ---- hub ----

    def _transit_gateway(self) -> None:
        self._add("TransitGateway", "AWS::EC2::TransitGateway", {
            "AmazonSideAsn": 64512, "AutoAcceptSharedAttachments": "disable", "DefaultRouteTableAssociation": "disable",
            "DefaultRouteTablePropagation": "disable", "DnsSupport": "enable", "VpnEcmpSupport": "enable",
            "Tags": _tags(f"{self._organization}-hub")})
        self._outputs["TransitGatewayId"] = {"Value": {"Ref": "TransitGateway"}}

    def _routing(self) -> None:
        tables = [pascal(ou.key) for ou in self._layout.environments]
        for table in [*tables, "Shared"]:
            self._add(f"RouteTable{table}", "AWS::EC2::TransitGatewayRouteTable", {
                "TransitGatewayId": {"Ref": "TransitGateway"}, "Tags": _tags(f"{self._organization}-rt-{table.lower()}")})
        for ou, table in zip(self._layout.environments, tables, strict=True):
            self._associate(table, table)
            self._propagate(table, table)
            if ou.tier != "sandbox":
                self._propagate("SharedServices", table)
            self._propagate(table, "Shared")
            if self._central:
                self._default_route(table)
        self._associate("SharedServices", "Shared")
        self._propagate("SharedServices", "Shared")
        if self._central:
            self._associate("Egress", "Shared")
            self._default_route("Shared")

    def _associate(self, attachment: str, table: str) -> None:
        self._add(f"Association{attachment}", "AWS::EC2::TransitGatewayRouteTableAssociation", {
            "TransitGatewayAttachmentId": {"Ref": f"Attachment{attachment}"},
            "TransitGatewayRouteTableId": {"Ref": f"RouteTable{table}"}})

    def _propagate(self, attachment: str, table: str) -> None:
        self._add(f"Propagation{attachment}To{table}", "AWS::EC2::TransitGatewayRouteTablePropagation", {
            "TransitGatewayAttachmentId": {"Ref": f"Attachment{attachment}"},
            "TransitGatewayRouteTableId": {"Ref": f"RouteTable{table}"}})

    def _default_route(self, table: str) -> None:
        self._add(f"EgressRoute{table}", "AWS::EC2::TransitGatewayRoute", {
            "DestinationCidrBlock": ANYWHERE, "TransitGatewayAttachmentId": {"Ref": "AttachmentEgress"},
            "TransitGatewayRouteTableId": {"Ref": f"RouteTable{table}"}})

    # ---- shared VPCs ----

    def _shared_vpc(self, key: str, label: str, principal: str) -> None:
        vpc = f"Vpc{key}"
        self._add(vpc, "AWS::EC2::VPC", {
            "CidrBlock": {"Fn::FindInMap": ["Cidrs", {"Ref": "AWS::Region"}, key]}, "EnableDnsHostnames": True,
            "EnableDnsSupport": True, "Tags": _tags(f"{self._organization}-{label.lower().replace(' ', '-')}")})
        subnets = [f"Subnet{key}{suffix}" for suffix in "AB"]
        for index, subnet in enumerate(subnets):
            self._add(subnet, "AWS::EC2::Subnet", {"VpcId": {"Ref": vpc}, "AvailabilityZone": _az(index),
                                                   "CidrBlock": _subnet_cidr(vpc, index, 4, 12),
                                                   "Tags": _tags(f"{label} private {'AB'[index]}")})
        self._add(f"PrivateRouteTable{key}", "AWS::EC2::RouteTable", {"VpcId": {"Ref": vpc}})
        for subnet in subnets:
            self._add(f"{subnet}RouteTableAssociation", "AWS::EC2::SubnetRouteTableAssociation", {
                "SubnetId": {"Ref": subnet}, "RouteTableId": {"Ref": f"PrivateRouteTable{key}"}})
        if self._hub:
            self._add(f"Attachment{key}", "AWS::EC2::TransitGatewayVpcAttachment", {
                "TransitGatewayId": {"Ref": "TransitGateway"}, "VpcId": {"Ref": vpc},
                "SubnetIds": [{"Ref": subnet} for subnet in subnets]})
            destination = ANYWHERE if self._central else self._cidr
            self._add(f"HubRoute{key}", "AWS::EC2::Route", {
                "RouteTableId": {"Ref": f"PrivateRouteTable{key}"}, "DestinationCidrBlock": destination,
                "TransitGatewayId": {"Ref": "TransitGateway"}}, [f"Attachment{key}"])
        if not self._central:
            self._local_egress(key, vpc)
        group = f"OrgSecurityGroup{key}"
        self._add(group, "AWS::EC2::SecurityGroup", {
            "GroupDescription": f"Organization security group for {label}: open inside the environment range",
            "VpcId": {"Ref": vpc}, "SecurityGroupIngress": [{
                "IpProtocol": "-1", "CidrIp": {"Fn::GetAtt": [vpc, "CidrBlock"]},
                "Description": f"Anything inside the {label} environment"}]})
        shared = [*(f"subnet/${{{subnet}}}" for subnet in subnets), f"security-group/${{{group}}}"]
        self._add(f"Share{key}", "AWS::RAM::ResourceShare", {
            "Name": f"{self._organization}-{key.lower()}-network", "AllowExternalPrincipals": False,
            "Principals": [{"Ref": principal}],
            "ResourceArns": [{"Fn::Sub": f"arn:${{AWS::Partition}}:ec2:${{AWS::Region}}:${{AWS::AccountId}}:{item}"}
                             for item in shared]})
        self._outputs |= {f"{vpc}Id": {"Value": {"Ref": vpc}},
                          f"{vpc}PrivateSubnetIds": {"Value": {"Fn::Join": [",", [{"Ref": subnet} for subnet in subnets]]}},
                          f"{vpc}Cidr": {"Value": {"Fn::GetAtt": [vpc, "CidrBlock"]}},
                          f"{vpc}SecurityGroupId": {"Value": {"Ref": group}}}

    def _local_egress(self, key: str, vpc: str) -> None:
        public = f"PublicSubnet{key}"
        self._add(public, "AWS::EC2::Subnet", {"VpcId": {"Ref": vpc}, "AvailabilityZone": _az(0),
                                               "CidrBlock": _subnet_cidr(vpc, 2, 4, 12)})
        self._internet_path(key, vpc, public, f"PrivateRouteTable{key}")

    def _internet_path(self, key: str, vpc: str, public_subnet: str, private_table: str | None) -> None:
        """Internet gateway, public route table and one NAT gateway; private_table gets a default route to the NAT."""
        self._add(f"Igw{key}", "AWS::EC2::InternetGateway", {})
        self._add(f"IgwAttachment{key}", "AWS::EC2::VPCGatewayAttachment", {
            "VpcId": {"Ref": vpc}, "InternetGatewayId": {"Ref": f"Igw{key}"}})
        self._add(f"PublicRouteTable{key}", "AWS::EC2::RouteTable", {"VpcId": {"Ref": vpc}})
        self._add(f"PublicRoute{key}", "AWS::EC2::Route", {
            "RouteTableId": {"Ref": f"PublicRouteTable{key}"}, "DestinationCidrBlock": ANYWHERE,
            "GatewayId": {"Ref": f"Igw{key}"}}, [f"IgwAttachment{key}"])
        self._add(f"{public_subnet}RouteTableAssociation", "AWS::EC2::SubnetRouteTableAssociation", {
            "SubnetId": {"Ref": public_subnet}, "RouteTableId": {"Ref": f"PublicRouteTable{key}"}})
        self._add(f"NatIp{key}", "AWS::EC2::EIP", {"Domain": "vpc"}, [f"IgwAttachment{key}"])
        self._add(f"Nat{key}", "AWS::EC2::NatGateway", {
            "SubnetId": {"Ref": public_subnet}, "AllocationId": {"Fn::GetAtt": [f"NatIp{key}", "AllocationId"]}})
        if private_table:
            self._add(f"NatRoute{key}", "AWS::EC2::Route", {
                "RouteTableId": {"Ref": private_table}, "DestinationCidrBlock": ANYWHERE,
                "NatGatewayId": {"Ref": f"Nat{key}"}})

    # ---- central egress and inspection ----

    def _egress_vpc(self) -> None:
        vpc = "VpcEgress"
        self._add(vpc, "AWS::EC2::VPC", {"CidrBlock": {"Fn::FindInMap": ["Cidrs", {"Ref": "AWS::Region"}, "Egress"]},
                                         "EnableDnsHostnames": True, "EnableDnsSupport": True,
                                         "Tags": _tags(f"{self._organization}-egress")})
        groups = {"Tgw": 0, "Firewall": 2, "Public": 4} if self._inspection else {"Tgw": 0, "Public": 4}
        for group, start in groups.items():
            for index in range(2):
                self._add(f"Egress{group}Subnet{'AB'[index]}", "AWS::EC2::Subnet", {
                    "VpcId": {"Ref": vpc}, "AvailabilityZone": _az(index),
                    "CidrBlock": _subnet_cidr(vpc, start + index, 6, 8)})
        self._internet_path("Egress", vpc, "EgressPublicSubnetA", None)
        self._add("AttachmentEgress", "AWS::EC2::TransitGatewayVpcAttachment", {
            "TransitGatewayId": {"Ref": "TransitGateway"}, "VpcId": {"Ref": vpc},
            "SubnetIds": [{"Ref": "EgressTgwSubnetA"}, {"Ref": "EgressTgwSubnetB"}],
            "Options": {"ApplianceModeSupport": "enable"}})
        toward_internet = {"VpcEndpointId": FIREWALL_ENDPOINT} if self._inspection else {"NatGatewayId": {"Ref": "NatEgress"}}
        self._table("EgressTgw", ["EgressTgwSubnetA", "EgressTgwSubnetB"], {ANYWHERE: toward_internet})
        back_to_hub = {"TransitGatewayId": {"Ref": "TransitGateway"}}
        self._add("PublicReturnRouteEgress", "AWS::EC2::Route", {
            "RouteTableId": {"Ref": "PublicRouteTableEgress"}, "DestinationCidrBlock": self._cidr,
            **({"VpcEndpointId": FIREWALL_ENDPOINT} if self._inspection else back_to_hub)}, ["AttachmentEgress"])
        self._add("PublicSubnetBRouteTableAssociationEgress", "AWS::EC2::SubnetRouteTableAssociation", {
            "SubnetId": {"Ref": "EgressPublicSubnetB"}, "RouteTableId": {"Ref": "PublicRouteTableEgress"}})
        if self._inspection:
            self._table("EgressFirewall", ["EgressFirewallSubnetA", "EgressFirewallSubnetB"],
                        {ANYWHERE: {"NatGatewayId": {"Ref": "NatEgress"}}, self._cidr: back_to_hub})
            self._firewall(vpc)

    def _table(self, key: str, subnets: list[str], routes: dict[str, dict]) -> None:
        self._add(f"{key}RouteTable", "AWS::EC2::RouteTable", {"VpcId": {"Ref": "VpcEgress"}})
        for subnet in subnets:
            self._add(f"{subnet}RouteTableAssociation", "AWS::EC2::SubnetRouteTableAssociation", {
                "SubnetId": {"Ref": subnet}, "RouteTableId": {"Ref": f"{key}RouteTable"}})
        for index, (destination, target) in enumerate(routes.items()):
            self._add(f"{key}Route{index}", "AWS::EC2::Route", {
                "RouteTableId": {"Ref": f"{key}RouteTable"}, "DestinationCidrBlock": destination, **target},
                ["AttachmentEgress"])

    def _firewall(self, vpc: str) -> None:
        name = f"{self._organization}-egress"
        self._add("FirewallRules", "AWS::NetworkFirewall::RuleGroup", {
            "RuleGroupName": f"{name}-rules", "Type": "STATEFUL", "Capacity": 1000,
            "RuleGroup": {"RuleVariables": {"IPSets": {"HOME_NET": {"Definition": [self._cidr]}}},
                          "RulesSource": {"RulesString": FirewallRules(self._context, self._layout).text()}}})
        self._add("FirewallPolicy", "AWS::NetworkFirewall::FirewallPolicy", {
            "FirewallPolicyName": f"{name}-policy", "FirewallPolicy": {
                "StatelessDefaultActions": ["aws:forward_to_sfe"],
                "StatelessFragmentDefaultActions": ["aws:forward_to_sfe"],
                "StatefulRuleGroupReferences": [{"ResourceArn": {"Ref": "FirewallRules"}}]}})
        self._add("Firewall", "AWS::NetworkFirewall::Firewall", {
            "FirewallName": name, "FirewallPolicyArn": {"Ref": "FirewallPolicy"}, "VpcId": {"Ref": vpc},
            "SubnetMappings": [{"SubnetId": {"Ref": "EgressFirewallSubnetA"}},
                               {"SubnetId": {"Ref": "EgressFirewallSubnetB"}}]})

