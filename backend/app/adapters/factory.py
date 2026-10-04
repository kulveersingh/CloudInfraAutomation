from app.adapters.local_aws import LocalAws
from app.adapters.local_github import LocalGitHub
from app.adapters.ports import AwsPort, GitHubPort
from app.config import Settings


class UnsupportedAdapterModeError(ValueError):
    pass


class AdapterFactory:
    """Creates GitHub and AWS adapters by mode. Real adapters are added with register_*()."""

    def __init__(self):
        self._github: dict[str, type[GitHubPort]] = {"local": LocalGitHub}
        self._aws: dict[str, type[AwsPort]] = {"local": LocalAws}

    def register_github(self, mode: str, adapter_class: type[GitHubPort]) -> None:
        self._github[mode] = adapter_class

    def register_aws(self, mode: str, adapter_class: type[AwsPort]) -> None:
        self._aws[mode] = adapter_class

    def github(self, settings: Settings) -> GitHubPort:
        return self._adapter_class(self._github, settings.github_mode, "GitHub").from_settings(settings)

    def aws(self, settings: Settings) -> AwsPort:
        return self._adapter_class(self._aws, settings.aws_mode, "AWS").from_settings(settings)

    def _adapter_class(self, classes: dict, mode: str, label: str):
        if mode not in classes:
            raise UnsupportedAdapterModeError(f"No {label} adapter registered for mode '{mode}'.")
        return classes[mode]
