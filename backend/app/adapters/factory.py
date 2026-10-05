from app.adapters.local_aws import LocalAws
from app.adapters.local_gcp import LocalGcp
from app.adapters.local_github import LocalGitHub
from app.adapters.ports import CloudPorts, GitHubPort, ProviderPort
from app.config import Settings
from app.landing_zone.executor import LandingZoneExecutor
from app.providers.aws.landing_zone.local_executor import LocalLandingZoneExecutor
from app.releases.executor import LocalReleaseExecutor, ReleaseExecutor


class UnsupportedAdapterModeError(ValueError):
    pass


class AdapterFactory:
    """Creates the GitHub adapter and one adapter per cloud provider, by mode. Real ones are added with register_*()."""

    def __init__(self):
        self._github: dict[str, type[GitHubPort]] = {"local": LocalGitHub}
        self._clouds: dict[str, dict[str, type[ProviderPort]]] = {"aws": {"local": LocalAws}, "gcp": {"local": LocalGcp}}
        self._executors: dict[str, type[ReleaseExecutor]] = {"local": LocalReleaseExecutor}
        self._landing_zone: dict[str, type[LandingZoneExecutor]] = {"local": LocalLandingZoneExecutor}

    def register_github(self, mode: str, adapter_class: type[GitHubPort]) -> None:
        self._github[mode] = adapter_class

    def register_cloud(self, provider: str, mode: str, adapter_class: type[ProviderPort]) -> None:
        self._clouds.setdefault(provider, {})[mode] = adapter_class

    def github(self, settings: Settings) -> GitHubPort:
        return self._adapter_class(self._github, settings.github_mode, "GitHub").from_settings(settings)

    def clouds(self, settings: Settings) -> CloudPorts:
        return CloudPorts({provider: self._adapter_class(classes, settings.cloud_mode(provider),
                                                         f"{provider} cloud").from_settings(settings)
                           for provider, classes in self._clouds.items()})

    def release_executor(self, settings: Settings) -> ReleaseExecutor:
        return self._adapter_class(self._executors, settings.aws_mode, "release executor").from_settings(settings)

    def landing_zone_executor(self, settings: Settings) -> LandingZoneExecutor:
        return self._adapter_class(self._landing_zone, settings.aws_mode, "landing zone executor").from_settings(settings)

    def _adapter_class(self, classes: dict, mode: str, label: str):
        if mode not in classes:
            raise UnsupportedAdapterModeError(f"No {label} adapter registered for mode '{mode}'.")
        return classes[mode]
