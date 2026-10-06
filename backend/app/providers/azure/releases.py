"""Release rows on Azure: what holds data, what changes permissions, and what-if results (MC4-9)."""

from app.releases.plan import ChangeSpec
from app.releases.risk import ResourceClassifier, RiskLevel, RiskRule

# Resource types (and their children) that hold data, lowercase.
STATEFUL_PREFIXES = ("microsoft.storage/storageaccounts", "microsoft.documentdb/", "microsoft.sql/",
                     "microsoft.dbforpostgresql/", "microsoft.dbformysql/", "microsoft.servicebus/",
                     "microsoft.keyvault/")
PERMISSION_PREFIXES = ("microsoft.authorization/", "microsoft.managedidentity/")
PERMISSION_SUFFIXES = ("/sqlroleassignments", "/sqlroledefinitions")
ACTIONS = {"Create": "Add", "Modify": "Modify", "Deploy": "Modify"}
PROVIDERS = "/providers/"


class StatefulModificationRule(RiskRule):
    """What-if cannot show that a change replaces a resource, so any change to data is at least medium risk."""

    def __init__(self, resources: ResourceClassifier):
        self._resources = resources

    def risk_of(self, change):
        return RiskLevel.MEDIUM if change.action == "Modify" and self._resources.is_stateful(change.resource_type) \
            else None


class AzureResourceClassifier(ResourceClassifier):
    """Which ARM resource types hold data, and which change permissions. Rows are `{stack}/{type}/{service}`."""

    def is_stateful(self, resource_type):
        return resource_type.lower().startswith(STATEFUL_PREFIXES)

    def is_permission(self, resource_type):
        lowered = resource_type.lower()
        return lowered.startswith(PERMISSION_PREFIXES) or lowered.endswith(PERMISSION_SUFFIXES)

    def rules(self):
        return [StatefulModificationRule(self)]

    def rows(self, document):
        rows, seen = [], {}
        for stack, template in document.items():
            for resource in template["resources"]:
                address = f"{stack}/{resource['type']}/{resource['comments']}"
                seen[address] = seen.get(address, 0) + 1
                rows.append((address if seen[address] == 1 else f"{address} #{seen[address]}", resource["type"]))
        return rows


class WhatIfReader:
    """Release rows from `az deployment group what-if` of one stack's template (JSON output). A delete counts only
    for a resource the stack manages (`az stack group show`): complete mode lists the other stacks' resources too,
    and the data stack (`detachAll`) never deletes, so it is read without `managed`."""

    def changes(self, result: dict, managed: set[str] | None = None) -> list[ChangeSpec]:
        own = {resource_id.lower() for resource_id in managed or ()}
        rows = []
        for change in result.get("changes", []):
            resource_id, kind = change["resourceId"], change["changeType"]
            action = "Remove" if kind == "Delete" and resource_id.lower() in own else ACTIONS.get(kind)
            if action:
                rows.append(ChangeSpec(action=action, logical_id=resource_id, resource_type=resource_type(resource_id)))
        return rows


def resource_type(resource_id: str) -> str:
    """`…/providers/Microsoft.Storage/storageAccounts/a/blobServices/default/containers/b` →
    `Microsoft.Storage/storageAccounts/blobServices/containers`; an extension resource's type is its own."""
    namespace, *path = resource_id.rsplit(PROVIDERS, 1)[1].split("/")
    return "/".join([namespace, *path[0::2]])
