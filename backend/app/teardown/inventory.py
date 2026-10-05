from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.synth.request import ProjectRequest


@dataclass(frozen=True)
class DataStore:
    """A resource that holds data, in one isolation unit and region: backed up before any teardown deletes it."""

    service_id: str
    logical_id: str
    resource_type: str
    physical_name: str
    region: str
    account_id: str
    source_ref: str
    retained: bool  # a retain policy keeps it after the deploy unit is deleted, so the teardown deletes it itself

    def preview(self) -> dict:
        return {"service_id": self.service_id, "resource_type": self.resource_type,
                "physical_name": self.physical_name, "region": self.region, "retained": self.retained}


class DataStoreInventory(ABC):
    """Finds the data stores an environment runs, from the document its current request generates."""

    @abstractmethod
    def for_environment(self, request: ProjectRequest, environment: str, account_id: str,
                        regions: list[str]) -> tuple[list[DataStore], list[str]]:
        """The data stores, and why any of them cannot be backed up."""

    @abstractmethod
    def not_backed_up(self, request: ProjectRequest) -> list[str]:
        ...


@dataclass(frozen=True)
class TeardownToolkit:
    """What a provider gives teardowns (§21.9): its data stores, what its backup service cannot keep, and the name
    of the locked central vault per region."""

    inventory: DataStoreInventory
    notes: tuple[str, ...]
    vault_pattern: str

    def vault_name(self, region: str) -> str:
        return self.vault_pattern.format(region=region)
