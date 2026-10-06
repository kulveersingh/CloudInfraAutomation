import re

GUID = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
NAME = r"[A-Za-z0-9][A-Za-z0-9._-]{0,78}[A-Za-z0-9_]?"
GROUP = r"[A-Za-z0-9._()-]{1,90}"
SUBSCRIPTION = re.compile(rf"^{GUID}$")
VNET = re.compile(rf"^/subscriptions/{GUID}/resourceGroups/{GROUP}/providers/Microsoft\.Network/virtualNetworks/{NAME}$")
NSG = re.compile(rf"^/subscriptions/{GUID}/resourceGroups/{GROUP}/providers/Microsoft\.Network/"
                 rf"networkSecurityGroups/{NAME}$")


def azure_network_problems(network) -> list[str]:
    """A spoke VNet in the environment's subscription: its subnets (the first delegated to Flex Consumption
    functions) and the network security groups on them (§22.11.5)."""
    problems = [] if SUBSCRIPTION.match(network.account_id) else ["Azure subscription ids are GUIDs."]
    if not VNET.match(network.network_ref):
        return [*problems, (f"'{network.network_ref}' is not a VNet "
                           "(/subscriptions/…/resourceGroups/…/providers/Microsoft.Network/virtualNetworks/…).")]
    subnet = re.compile(rf"^{re.escape(network.network_ref)}/subnets/{NAME}$")
    problems += [f"'{ref}' is not a subnet of {network.network_ref}." for ref in network.subnet_refs
                 if not subnet.match(ref)]
    return problems + [f"'{ref}' is not a network security group "
                       "(/subscriptions/…/providers/Microsoft.Network/networkSecurityGroups/…)."
                       for ref in network.firewall_refs if not NSG.match(ref)]
