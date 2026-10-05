import re

PROJECT_ID = r"[a-z][a-z0-9-]{4,28}[a-z0-9]"
NAME = r"[a-z]([-a-z0-9]{0,61}[a-z0-9])?"
PROJECT = re.compile(rf"^{PROJECT_ID}$")
NETWORK = re.compile(rf"^projects/{PROJECT_ID}/global/networks/{NAME}$")
TAG = re.compile(rf"^{NAME}$")


def gcp_network_problems(network) -> list[str]:
    """A Shared VPC network: the host project's network, regional subnetworks, and network tags for firewalls."""
    problems = [] if PROJECT.match(network.account_id) else [
        "Google Cloud project ids are 6 to 30 lowercase letters, digits and hyphens."]
    problems += [] if NETWORK.match(network.network_ref) else [
        f"'{network.network_ref}' is not a VPC network (projects/…/global/networks/…)."]
    subnetwork = re.compile(rf"^projects/{PROJECT_ID}/regions/{re.escape(network.region)}/subnetworks/{NAME}$")
    problems += [f"'{subnet}' is not a subnetwork in {network.region} "
                 f"(projects/…/regions/{network.region}/subnetworks/…)." for subnet in network.subnet_refs
                 if not subnetwork.match(subnet)]
    return problems + [f"'{tag}' is not a network tag (lowercase letters, digits and hyphens)."
                       for tag in network.firewall_refs if not TAG.match(tag)]
