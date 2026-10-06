from app.providers.gcp.landing_zone.deployments.base import (
    HUB_SLOT,
    ORGANIZATION,
    Deployment,
    DeploymentContext,
    resource_name,
)

FLOW_SAMPLING = 0.5
FIREWALL_ZONE = "b"


class NetworkDeployment(Deployment):
    """The hub at the center of an NCC star, one Shared VPC per environment as an edge (no route between
    environments), Cloud NAT per environment and region, declared flows as Private Service Connect endpoints, and
    optional hybrid links and NGFW inspection on the hub (MC3-3)."""

    name = "lz-network"
    description = "Hub and NCC star, Shared VPC per environment, Cloud NAT, flows, hybrid and inspection"

    def build(self, context, document):
        hub_project = context.unit("network")
        self._vpc(context, document, HUB_SLOT, hub_project)
        document.add_resource("google_network_connectivity_hub", "hub", {
            "project": hub_project, "name": f"{context.design.answers.organization_name}-hub",
            "preset_topology": "STAR", "description": "Shared services and hybrid links at the center"})
        self._spoke(document, HUB_SLOT, hub_project, "center")
        for environment in context.environments:
            key, host = environment.ou.key, environment.host.name
            document.add_resource("google_compute_shared_vpc_host_project", key, {"project": host})
            self._vpc(context, document, key, host)
            self._spoke(document, key, host, "edge")
            for workload in environment.workloads:
                document.add_resource("google_compute_shared_vpc_service_project", workload.name, {
                    "host_project": host, "service_project": workload.name,
                    "depends_on": [f"google_compute_shared_vpc_host_project.{key}"]})
        self._flows(context, document)
        self._hybrid(context, document, hub_project)
        self._inspection(context, document, hub_project)

    def _vpc(self, context: DeploymentContext, document, key: str, project: str) -> None:
        document.add_resource("google_compute_network", key, {
            "project": project, "name": f"vpc-{resource_name(key)}", "auto_create_subnetworks": False,
            "routing_mode": "GLOBAL"})
        for region in context.regions:
            name = f"{key}-{region}"
            document.add_resource("google_compute_subnetwork", name, {
                "project": project, "name": f"{resource_name(key)}-{region}", "region": region,
                "network": f"${{google_compute_network.{key}.id}}", "ip_cidr_range": context.subnet(key, region),
                "private_ip_google_access": True,
                "log_config": {"aggregation_interval": "INTERVAL_5_SEC", "flow_sampling": FLOW_SAMPLING}})
            if key != HUB_SLOT:
                self._nat(document, name, project, key, region)

    def _nat(self, document, name: str, project: str, key: str, region: str) -> None:
        document.add_resource("google_compute_router", name, {
            "project": project, "name": f"{resource_name(key)}-{region}", "region": region,
            "network": f"${{google_compute_network.{key}.id}}"})
        document.add_resource("google_compute_router_nat", name, {
            "project": project, "name": f"{resource_name(key)}-{region}", "region": region,
            "router": f"${{google_compute_router.{name}.name}}", "nat_ip_allocate_option": "AUTO_ONLY",
            "source_subnetwork_ip_ranges_to_nat": "ALL_SUBNETWORKS_ALL_IP_RANGES",
            "log_config": {"enable": True, "filter": "ERRORS_ONLY"}})

    def _spoke(self, document, key: str, project: str, group: str) -> None:
        document.add_resource("google_network_connectivity_spoke", key, {
            "project": project, "name": f"{resource_name(key)}-spoke", "location": "global",
            "hub": "${google_network_connectivity_hub.hub.id}",
            "group": f"${{google_network_connectivity_hub.hub.id}}/groups/{group}",
            "linked_vpc_network": {"uri": f"${{google_compute_network.{key}.self_link}}"}})

    def _flows(self, context, document) -> None:
        """Each declared flow: the destination publishes its service; the source gets an endpoint to it, once its
        service attachment is known (an input, empty until then)."""
        home = context.design.answers.home_region
        hosts = {environment.ou.key: environment.host.name for environment in context.environments}
        for index, flow in enumerate(context.design.answers.network.flows, start=1):
            variable = f"flow_{index}_service_attachment"
            document.add_variable(variable, {"type": "string", "default": "", "description": (
                f"{flow.source} → {flow.destination} on {flow.protocol}/{flow.port}: {flow.reason}")})
            present = f'${{var.{variable} == "" ? 0 : 1}}'
            source = hosts[flow.source]
            document.add_resource("google_compute_address", f"flow-{index}", {
                "count": present, "project": source, "name": f"flow-{index}-{resource_name(flow.destination)}",
                "region": home, "address_type": "INTERNAL",
                "subnetwork": f"${{google_compute_subnetwork.{flow.source}-{home}.id}}"})
            document.add_resource("google_compute_forwarding_rule", f"flow-{index}", {
                "count": present, "project": source, "name": f"flow-{index}-{resource_name(flow.destination)}",
                "region": home, "target": f"${{var.{variable}}}", "load_balancing_scheme": "",
                "network": f"${{google_compute_network.{flow.source}.id}}",
                "ip_address": f"${{google_compute_address.flow-{index}[0].id}}"})

    def _hybrid(self, context, document, hub_project: str) -> None:
        if context.design.answers.network.on_premises != "vpn":
            return
        home = context.design.answers.home_region
        document.add_resource("google_compute_ha_vpn_gateway", "hub", {
            "project": hub_project, "name": "hub-vpn", "region": home, "network": "${google_compute_network.hub.id}"})

    def _inspection(self, context, document, hub_project: str) -> None:
        if not context.design.answers.network.inspection:
            return
        for region in context.regions:
            zone = f"{region}-{FIREWALL_ZONE}"
            document.add_resource("google_network_security_firewall_endpoint", region, {
                "parent": ORGANIZATION, "name": f"{context.design.answers.organization_name}-ngfw-{zone}",
                "location": zone, "billing_project_id": "${var.seed_project}"})
            document.add_resource("google_network_security_firewall_endpoint_association", region, {
                "parent": f"projects/{hub_project}", "name": f"hub-{zone}", "location": zone,
                "network": "${google_compute_network.hub.id}",
                "firewall_endpoint": f"${{google_network_security_firewall_endpoint.{region}.id}}"})
