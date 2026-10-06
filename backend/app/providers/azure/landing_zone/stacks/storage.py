"""A storage account whose blobs cannot be changed or deleted for a number of days (locked version-level
immutability), for logs and teardown exports."""

STORAGE_API = "2023-05-01"


def locked_account(name: str, location: str, days: int, container: str | None = None,
                   tags: dict | None = None) -> list[dict]:
    service = f"[format('{{0}}/default', {name[1:-1]})]"
    resources = [{"type": "Microsoft.Storage/storageAccounts", "apiVersion": STORAGE_API, "name": name,
                  "location": location, "kind": "StorageV2", "sku": {"name": "Standard_ZRS"}, **({"tags": tags} if tags else {}),
                  "properties": {"allowSharedKeyAccess": False, "allowBlobPublicAccess": False,
                                 "minimumTlsVersion": "TLS1_2", "supportsHttpsTrafficOnly": True,
                                 "immutableStorageWithVersioning": {"enabled": True, "immutabilityPolicy": {
                                     "immutabilityPeriodSinceCreationInDays": days, "state": "Locked",
                                     "allowProtectedAppendWrites": False}}}},
                 {"type": "Microsoft.Storage/storageAccounts/blobServices", "apiVersion": STORAGE_API,
                  "name": service, "dependsOn": [name],
                  "properties": {"isVersioningEnabled": True}}]
    if container:
        resources.append({"type": "Microsoft.Storage/storageAccounts/blobServices/containers", "apiVersion": STORAGE_API,
                          "name": f"[format('{{0}}/default/{container}', {name[1:-1]})]",
                          "dependsOn": [service],
                          "properties": {"publicAccess": "None"}})
    return resources
