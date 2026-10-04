from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.config import Settings


class RepositoryConflictError(Exception):
    """The repository exists but was not created by this provisioning request."""


@dataclass(frozen=True)
class BootstrapRequest:
    account_id: str
    region: str
    project: str
    repository: str
    environment: str

    @property
    def stack_name(self) -> str:
        return f"cloudinfra-bootstrap-{self.project}"

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
    deploy_role_arn: str
    cfn_execution_role_arn: str


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
    def commit_files(self, owner: str, name: str, files: dict[str, str], message: str) -> str:
        ...

    @abstractmethod
    def read_files(self, owner: str, name: str) -> RepositorySnapshot:
        ...

    @abstractmethod
    def set_repository_properties(self, owner: str, name: str, properties: dict[str, str]) -> None:
        """GitHub repository custom properties (topics on personal-account repositories)."""

    @abstractmethod
    def repository_properties(self, owner: str, name: str) -> dict[str, str]:
        ...


class AwsPort(ABC):
    """What the platform needs from AWS to bootstrap a project in an account and region."""

    @classmethod
    @abstractmethod
    def from_settings(cls, settings: Settings) -> "AwsPort":
        ...

    @abstractmethod
    def ensure_bootstrap_stack(self, request: BootstrapRequest) -> BootstrapOutputs:
        ...

    @abstractmethod
    def delete_bootstrap_stack(self, request: BootstrapRequest) -> None:
        ...
