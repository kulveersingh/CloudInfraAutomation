from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from app.config import Settings
from app.errors import NotFoundError

DEFAULT_BRANCH = "main"
BOOTSTRAP_STACK = "cloudinfra-bootstrap-{project}"


class RepositoryConflictError(Exception):
    """The repository exists but was not created by this provisioning request."""


class MergeConflictError(Exception):
    """The pull request cannot be merged or closed in its current state."""


class RepositoryArchivedError(Exception):
    """The repository is archived (read-only)."""


@dataclass(frozen=True)
class PullRequest:
    number: int
    url: str


@dataclass(frozen=True)
class BootstrapRequest:
    account_id: str
    region: str
    project: str
    repository: str
    environment: str

    @property
    def stack_name(self) -> str:
        return BOOTSTRAP_STACK.format(project=self.project)

    @property
    def trust_subject(self) -> str:
        return f"repo:{self.repository}:environment:{self.environment}"


@dataclass(frozen=True)
class RepositorySnapshot:
    """The files on the default branch and the commit they come from (None for a repository with no commits)."""

    commit_sha: str | None
    files: dict[str, str]


@dataclass(frozen=True)
class BootstrapOutputs:
    deployer_identity: str  # what the deploy workflow signs in as (AWS: the deploy role)
    execution_identity: str  # what applies the IaC document (AWS: the CloudFormation execution role)


class GitHubPort(ABC):
    """What the platform needs from GitHub. Implementations: LocalGitHub now, a GitHub App client later."""

    @classmethod
    @abstractmethod
    def from_settings(cls, settings: Settings) -> "GitHubPort":
        ...

    @abstractmethod
    def create_repository(self, owner: str, name: str, marker: str) -> bool:
        ...

    @abstractmethod
    def repository_exists(self, owner: str, name: str) -> bool:
        ...

    @abstractmethod
    def delete_repository(self, owner: str, name: str) -> None:
        ...

    @abstractmethod
    def set_repository_variables(self, owner: str, name: str, variables: dict[str, str]) -> None:
        ...

    @abstractmethod
    def set_environment(self, owner: str, name: str, environment: str, variables: dict[str, str]) -> None:
        ...

    @abstractmethod
    def commit_files(self, owner: str, name: str, files: dict[str, str], message: str,
                     branch: str = DEFAULT_BRANCH, deleted: tuple[str, ...] | list[str] = ()) -> str:
        """One commit on the branch (a new branch starts from the default branch), also removing `deleted` paths."""

    @abstractmethod
    def read_files(self, owner: str, name: str, branch: str = DEFAULT_BRANCH) -> RepositorySnapshot:
        ...

    @abstractmethod
    def delete_branch(self, owner: str, name: str, branch: str) -> None:
        ...

    @abstractmethod
    def repository_variables(self, owner: str, name: str) -> dict[str, str]:
        ...

    @abstractmethod
    def delete_environment(self, owner: str, name: str, environment: str) -> None:
        ...

    @abstractmethod
    def archive_repository(self, owner: str, name: str) -> None:
        ...

    @abstractmethod
    def unarchive_repository(self, owner: str, name: str) -> None:
        ...

    @abstractmethod
    def open_pull_request(self, owner: str, name: str, branch: str, title: str, body: str) -> PullRequest:
        ...

    @abstractmethod
    def merge_pull_request(self, owner: str, name: str, number: int) -> str:
        """Local stand-in for a person merging in GitHub (§21.8 C2); returns the new default-branch commit."""

    @abstractmethod
    def close_pull_request(self, owner: str, name: str, number: int) -> None:
        ...

    @abstractmethod
    def set_repository_properties(self, owner: str, name: str, properties: dict[str, str]) -> None:
        """GitHub repository custom properties (topics on personal-account repositories)."""

    @abstractmethod
    def repository_properties(self, owner: str, name: str) -> dict[str, str]:
        ...


class ProviderPort(ABC):
    """What the platform needs from a cloud: bootstrap trust per environment, delete and adopt deploy units and
    data stores, and its backup service. Implementations: LocalAws now; one per cloud and mode later."""

    @classmethod
    @abstractmethod
    def from_settings(cls, settings: Settings) -> "ProviderPort":
        ...

    @abstractmethod
    def ensure_bootstrap_stack(self, request: BootstrapRequest) -> BootstrapOutputs:
        ...

    @abstractmethod
    def delete_bootstrap_stack(self, request: BootstrapRequest) -> None:
        ...

    @abstractmethod
    def allow_stack_deletion(self, account_id: str, region: str, stack_name: str) -> None:
        """Lifts the production stack policy for one deletion (§21.9.2)."""

    @abstractmethod
    def delete_stack(self, account_id: str, region: str, stack_name: str) -> None:
        ...

    @abstractmethod
    def delete_data_store(self, account_id: str, region: str, resource_type: str, physical_name: str) -> None:
        """Empties and deletes a data store a retain policy kept, once it is backed up."""

    @abstractmethod
    def import_stack(self, account_id: str, region: str, stack_name: str, logical_ids: list[str]) -> None:
        """Creates the stack with an IMPORT change set that adopts restored data stores (§21.9.5)."""

    @abstractmethod
    def backup(self, backup_account_id: str) -> "BackupPort":
        """AWS Backup, with the central vaults of the given Backup account."""


@dataclass(frozen=True)
class BackupSource:
    account_id: str
    region: str
    resource_type: str
    source_ref: str


@dataclass(frozen=True)
class RecoveryPoint:
    ref: str
    vault: str
    account_id: str
    region: str
    source_ref: str
    resource_type: str
    completed_at: datetime
    locked_until: datetime


@dataclass(frozen=True)
class VaultLock:
    locked: bool
    min_retention_days: int


class BackupPort(ABC):
    """A cloud's backup service for teardowns, from `ProviderPort.backup`: back up into the locked central vault, check the lock,
    restore. It has no way to delete a recovery point: only super users do that, manually, after the lock (§21.9.1)."""

    @abstractmethod
    def back_up(self, source: BackupSource) -> RecoveryPoint:
        """Backs up the resource and copies it to the central vault; returns once the copy completed."""

    @abstractmethod
    def vault_lock(self, region: str) -> VaultLock:
        ...

    @abstractmethod
    def recovery_point(self, ref: str) -> RecoveryPoint | None:
        ...

    @abstractmethod
    def restore(self, recovery_point_ref: str, account_id: str, region: str, physical_name: str) -> None:
        ...


class CloudPorts:
    """One adapter per cloud provider; work for a project uses its provider's adapter."""

    def __init__(self, ports: dict[str, ProviderPort]):
        self._ports = ports

    def get(self, provider: str) -> ProviderPort:
        if provider not in self._ports:
            raise NotFoundError(f"No adapter for cloud provider '{provider}'.")
        return self._ports[provider]
