"""The platform's own Azure Policy definitions (`cloudinfra-…`), defined once at the organization's management
group (§22.12.4). Rules are written as Azure Policy reads them; the stack escapes them for ARM."""

TYPE = "type"
SPECIAL_SUBNETS = ["GatewaySubnet", "AzureFirewallSubnet", "AzureFirewallManagementSubnet", "AzureBastionSubnet",
                   "RouteServerSubnet"]
GEO_REDUNDANT = ["Standard_GRS", "Standard_RAGRS", "Standard_GZRS", "Standard_RAGZRS"]
DELETE = {"effect": "denyAction", "details": {"actionNames": ["delete"]}}
DENY = {"effect": "deny"}


def _is(type_name: str) -> dict:
    return {"field": TYPE, "equals": type_name}


def _outside(field: str, subscription: str) -> dict:
    return {"field": field, "notContains": f"[concat('/subscriptions/', {subscription}, '/')]"}


def _connections(kind: str) -> dict:
    field = f"Microsoft.Network/privateEndpoints/{kind}[*]"
    return {"count": {"field": field, "where": _outside(f"{field}.privateLinkServiceId", "subscription().subscriptionId")},
            "greater": 0}


DEFINITIONS: dict[str, dict] = {
    "cloudinfra-deny-subnet-without-nsg": {"mode": "All", "policyRule": {"if": {"anyOf": [
        {"allOf": [_is("Microsoft.Network/virtualNetworks/subnets"), {"field": "name", "notIn": SPECIAL_SUBNETS},
                   {"field": "Microsoft.Network/virtualNetworks/subnets/networkSecurityGroup.id", "exists": False}]},
        {"allOf": [_is("Microsoft.Network/virtualNetworks"), {"count": {
            "field": "Microsoft.Network/virtualNetworks/subnets[*]", "where": {"allOf": [
                {"field": "Microsoft.Network/virtualNetworks/subnets[*].name", "notIn": SPECIAL_SUBNETS},
                {"field": "Microsoft.Network/virtualNetworks/subnets[*].networkSecurityGroup.id", "exists": False}]}},
            "greater": 0}]}]}, "then": DENY}},
    "cloudinfra-deny-subscription-role-assignments": {"mode": "All", "policyRule": {"if": {"allOf": [
        _is("Microsoft.Authorization/roleAssignments"), {"field": "id", "contains": "/subscriptions/"},
        {"field": "id", "notContains": "/resourceGroups/"}]}, "then": DENY}},
    "cloudinfra-deny-peering-outside-hub": {
        "mode": "All", "parameters": {"hubSubscriptionId": {"type": "String"}},
        "policyRule": {"if": {"allOf": [
            _is("Microsoft.Network/virtualNetworks/virtualNetworkPeerings"),
            _outside("Microsoft.Network/virtualNetworks/virtualNetworkPeerings/remoteVirtualNetwork.id",
                     "parameters('hubSubscriptionId')"),
            _outside("id", "parameters('hubSubscriptionId')")]}, "then": DENY}},
    "cloudinfra-deny-cross-environment-private-endpoints": {"mode": "All", "policyRule": {"if": {"allOf": [
        _is("Microsoft.Network/privateEndpoints"),
        {"anyOf": [_connections("privateLinkServiceConnections"), _connections("manualPrivateLinkServiceConnections")]}]},
        "then": DENY}},
    "cloudinfra-deny-delete-log-stores": {"mode": "Indexed", "policyRule": {"if": {"allOf": [
        {"field": TYPE, "in": ["Microsoft.OperationalInsights/workspaces", "Microsoft.Storage/storageAccounts"]},
        {"field": "tags['cloudinfra-role']", "equals": "logs"}]}, "then": DELETE}},
    "cloudinfra-deny-delete-data-stores": {"mode": "Indexed", "policyRule": {"if": {
        "field": TYPE, "in": ["Microsoft.Storage/storageAccounts", "Microsoft.DocumentDB/databaseAccounts",
                              "Microsoft.Sql/servers", "Microsoft.DataProtection/backupVaults"]}, "then": DELETE}},
    "cloudinfra-deny-geo-storage-outside-allowed-regions": {
        "mode": "Indexed", "parameters": {"allowedRegions": {"type": "Array"}},
        "policyRule": {"if": {"allOf": [
            _is("Microsoft.Storage/storageAccounts"),
            {"field": "Microsoft.Storage/storageAccounts/sku.name", "in": GEO_REDUNDANT},
            {"field": "location", "notIn": "[parameters('allowedRegions')]"}]}, "then": DENY}},
    "cloudinfra-deny-public-ip-addresses": {"mode": "All", "policyRule": {
        "if": _is("Microsoft.Network/publicIPAddresses"), "then": DENY}},
}
