import hashlib
import re
from dataclasses import dataclass

from app.adapters.ports import BOOTSTRAP_STACK
from app.providers.gcp.project.document import PRIMARY_ONLY
from app.providers.gcp.project.toolkit import gcp_project
from app.synth.blocks.registry import BlockRegistry
from app.synth.request import ProjectRequest
from app.synth.synthesizer import TemplateSynthesizer
from app.teardown.inventory import DataStore, DataStoreInventory, TeardownToolkit

SHORT_HASH = re.compile(r"\$\{substr\(sha1\(var\.(\w+)\), 0, (\d+)\)\}")
VARIABLE = re.compile(r"\$\{var\.(\w+)\}")
# Data the platform has no backup for yet: a teardown of an environment that holds them is refused (§22.9.5).
UNSUPPORTED_TYPES = frozenset({"google_spanner_instance", "google_spanner_database", "google_bigtable_instance",
                               "google_bigtable_table", "google_bigquery_dataset", "google_bigquery_table",
                               "google_filestore_instance"})
MISSING_VAULT = "No vault project is configured: set gcp_backup_project until the Google Cloud landing zone creates one."


@dataclass(frozen=True)
class GcpBackupTarget:
    """One kind of data store the vault project can keep. New data blocks add one (Open/Closed)."""

    type_name: str
    name_argument: str
    ref_pattern: str  # {name}, {account} (the environment project) and {region}

    def ref(self, name: str, account_id: str, region: str) -> str:
        return self.ref_pattern.format(name=name, account=account_id, region=region)

    def retained(self, body: dict) -> bool:
        """Kept after its deployment is deleted, so the teardown deletes it itself."""
        return body.get("deletion_policy") == "ABANDON"


TARGETS = (
    GcpBackupTarget("google_storage_bucket", "name", "projects/_/buckets/{name}"),
    GcpBackupTarget("google_firestore_database", "name", "projects/{account}/databases/{name}"),
    GcpBackupTarget("google_sql_database_instance", "name", "projects/{account}/instances/{name}"),
    GcpBackupTarget("google_alloydb_cluster", "cluster_id", "projects/{account}/locations/{region}/clusters/{name}"),
)


class TerraformNames:
    """Resolves a name written with Terraform expressions, for the variables a deployment gets."""

    def __init__(self, variables: dict[str, str]):
        self._variables = variables

    def resolve(self, text) -> str | None:
        if not isinstance(text, str):
            return None
        resolved = SHORT_HASH.sub(self._short_hash, text)
        resolved = VARIABLE.sub(lambda match: self._variables.get(match[1], match[0]), resolved)
        return None if "${" in resolved else resolved

    def _short_hash(self, match: re.Match) -> str:
        if match[1] not in self._variables:
            return match[0]
        return hashlib.sha1(self._variables[match[1]].encode()).hexdigest()[:int(match[2])]


class TerraformInventory(DataStoreInventory):
    """Finds an environment's data stores in the Terraform configuration its current request generates."""

    def __init__(self, synthesizer: TemplateSynthesizer, blocks: BlockRegistry, targets: tuple[GcpBackupTarget, ...]):
        self._synthesizer = synthesizer
        self._blocks = blocks
        self._targets = {target.type_name: target for target in targets}

    @classmethod
    def default(cls) -> "TerraformInventory":
        toolkit = gcp_project()
        return cls(toolkit.synthesizer, toolkit.blocks, TARGETS)

    def for_environment(self, request, environment, account_id, regions):
        names = TerraformNames({"project_name": request.project_name, "project_id": account_id,
                                "environment_name": environment})
        stores: list[DataStore] = []
        problems: list[str] = []
        for service_id, type_name, name, body in self._main_resources(request):
            if type_name in UNSUPPORTED_TYPES:
                problems.append(f"Cannot back up {service_id} ({type_name}): the platform has no backup for it yet.")
                continue
            target = self._targets.get(type_name)
            if target is None:
                continue
            physical_name = names.resolve(body.get(target.name_argument))
            if physical_name is None:
                problems.append(f"Cannot back up {service_id} ({type_name}): its name is not in the configuration.")
                continue
            for region in self._regions(body, regions, request.resilience.primary_region):
                stores.append(DataStore(service_id, f"{type_name}.{name}", type_name, physical_name, region, account_id,
                                        target.ref(physical_name, account_id, region), target.retained(body)))
        return stores, problems

    def not_backed_up(self, request: ProjectRequest) -> list[str]:
        held = {*self._targets, *UNSUPPORTED_TYPES}
        return [f"{service_id} ({request.resource(service_id).type}): rebuilt from the configuration and the "
                "application repository" for service_id, type_name, _, _ in self._main_resources(request)
                if type_name not in held]

    def _main_resources(self, request: ProjectRequest):
        document = self._synthesizer.synthesize(request)
        for spec in request.resources:
            type_name, name = self._blocks.create(spec, request).main_resource
            yield spec.id, type_name, name, document["resource"][type_name][name]

    def _regions(self, body: dict, regions: list[str], primary: str) -> list[str]:
        """A project-wide resource (a dual-region bucket, a multi-region database) is backed up once."""
        return [primary] if body.get("count") == PRIMARY_ONLY else regions


def gcp_teardown() -> TeardownToolkit:
    return TeardownToolkit(inventory=TerraformInventory.default(),
                           notes=("Pub/Sub messages: transient, not backed up", "Cloud Logging: keep logs with a log sink"),
                           vault_pattern="cloudinfra-teardown-{region}-{account}",
                           unit_patterns=("cloudinfra-{project}-{region}", BOOTSTRAP_STACK), missing_vault=MISSING_VAULT)
