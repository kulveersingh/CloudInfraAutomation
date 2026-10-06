"""Teardown on Azure (§22.11.6): data stores from the data template, backed up into the locked vault."""

from app.adapters.ports import BOOTSTRAP_STACK
from app.providers.azure.expressions import ArmExpressions
from app.providers.azure.naming import resource_group_id
from app.providers.azure.project.toolkit import azure_project
from app.providers.azure.provider import REGION_PAIRS
from app.providers.azure.releases import AzureResourceClassifier
from app.synth.request import ProjectRequest
from app.teardown.inventory import DataStore, DataStoreInventory, TeardownToolkit

# Kinds the backup subscription keeps: blobs in the locked Backup vault, Cosmos DB exported to a locked container.
BACKED_UP_TYPES = frozenset({"microsoft.storage/storageaccounts", "microsoft.documentdb/databaseaccounts"})
VAULT_PATTERN = ("/subscriptions/{account}/resourceGroups/rg-cloudinfra-backup/providers/"
                 "Microsoft.DataProtection/backupVaults/bv-teardown-{region}")
MISSING_VAULT = ("No backup subscription is configured: set azure_backup_subscription until the Azure landing zone "
                 "creates one.")
NOTES = ("Service Bus messages: transient, not backed up", "Logs: keep them with diagnostic settings",
         "The contract Key Vault: soft-deleted for 90 days, and recovered by the next deployment")


class AzureInventory(DataStoreInventory):
    """Finds an environment's data stores in the data template its current request generates. Everything there is
    deployed once, in the primary region; names are evaluated for the environment's resource group."""

    def __init__(self, synthesizer, classifier: AzureResourceClassifier | None = None):
        self._synthesizer = synthesizer
        self._classifier = classifier or AzureResourceClassifier()

    @classmethod
    def default(cls) -> "AzureInventory":
        return cls(azure_project(REGION_PAIRS.get).synthesizer)

    def for_environment(self, request, environment, account_id, regions):
        data = self._synthesizer.synthesize(request)["data"]
        group = resource_group_id(account_id, request.project_name, environment)
        primary = request.resilience.primary_region
        names = ArmExpressions({"projectName": request.project_name, "environmentName": environment,
                                "location": primary}, data["variables"], group)
        stores: list[DataStore] = []
        problems: list[str] = []
        for service_id, resource in self._held(request, data):
            type_name = resource["type"]
            if type_name.lower() not in BACKED_UP_TYPES:
                problems.append(f"Cannot back up {service_id} ({type_name}): the platform has no backup for it yet.")
                continue
            name = names.evaluate(resource["name"])
            if name is None:
                problems.append(f"Cannot back up {service_id} ({type_name}): its name is not in the template.")
                continue
            stores.append(DataStore(service_id, f"{type_name}/{name}", type_name, name, primary, account_id,
                                    f"{group}/providers/{type_name}/{name}", retained=False))
        return stores, problems

    def not_backed_up(self, request: ProjectRequest) -> list[str]:
        held = dict(self._held(request, self._synthesizer.synthesize(request)["data"]))
        return [f"{spec.id} ({spec.type}): rebuilt from the templates and the application repository"
                for spec in request.resources if spec.id not in held]

    def _held(self, request: ProjectRequest, data: dict):
        """Each service whose top-level resource in the data stack holds data: backed up, or blocking the teardown.
        The rest (compute, queues, caches) is rebuilt."""
        for spec in request.resources:
            found = next((resource for resource in data["resources"]
                          if resource.get("comments") == spec.id and resource["type"].count("/") == 1), None)
            if found is not None and self._classifier.is_stateful(found["type"]):
                yield spec.id, found


def azure_teardown() -> TeardownToolkit:
    return TeardownToolkit(inventory=AzureInventory.default(), notes=NOTES, vault_pattern=VAULT_PATTERN,
                           unit_patterns=("{project}-{region}", "{project}-shared", "{project}-data", BOOTSTRAP_STACK),
                           missing_vault=MISSING_VAULT)
