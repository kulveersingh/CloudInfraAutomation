"""Refreshes the bundled Azure resource types: `uv run python -m app.providers.azure.project.refresh`.

Reads Azure/bicep-types-az (network access needed): every type's API versions, and the property schemas of the API
versions the curated services pin."""

import json
import sys
import urllib.request
from functools import cache
from pathlib import Path

from app.providers.azure.project.schema import BUNDLED_PATH, BicepTypesReader

SOURCE = "https://raw.githubusercontent.com/Azure/bicep-types-az/main/generated/"
PINNED = [
    "Microsoft.Storage/storageAccounts@2023-05-01", "Microsoft.Storage/storageAccounts/blobServices@2023-05-01",
    "Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01",
    "Microsoft.Storage/storageAccounts/managementPolicies@2023-05-01", "Microsoft.Web/serverfarms@2024-04-01",
    "Microsoft.Web/sites@2024-04-01", "Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31",
    "Microsoft.DocumentDB/databaseAccounts@2024-11-15", "Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2024-11-15",
    "Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-11-15",
    "Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-11-15", "Microsoft.ServiceBus/namespaces@2024-01-01",
    "Microsoft.ServiceBus/namespaces/queues@2024-01-01", "Microsoft.Authorization/roleAssignments@2022-04-01",
    "Microsoft.EventGrid/systemTopics@2022-06-15", "Microsoft.EventGrid/systemTopics/eventSubscriptions@2022-06-15",
    "Microsoft.KeyVault/vaults@2023-07-01", "Microsoft.KeyVault/vaults/secrets@2023-07-01",
    "Microsoft.Network/privateEndpoints@2024-05-01",
]


TIMEOUT_SECONDS = 60


@cache
def fetch(path: str):
    """One file of the type repository; a provider's types.json serves several pinned types, so it is kept."""
    with urllib.request.urlopen(SOURCE + path, timeout=TIMEOUT_SECONDS) as response:
        return json.loads(response.read())


def main(argv: list[str], reader: BicepTypesReader | None = None, target: Path = BUNDLED_PATH,
         pinned: tuple[str, ...] | list[str] = PINNED) -> None:
    (reader or BicepTypesReader(fetch)).read(list(pinned)).write(target)
    print(f"Wrote Azure resource types to {target}")


if __name__ == "__main__":
    main(sys.argv[1:])
