from app.landing_zone.answers import LandingZoneAnswers
from app.landing_zone.repository import LandingZoneRepository
from app.providers.base import DEFAULT_PROVIDER, ProviderRegistry


class BackupAccountResolver:
    """Each cloud's central backup account (on Google Cloud, the vault project): configured explicitly, or the
    backup unit its applied landing zone vended (§21.9, §22.10.6)."""

    def __init__(self, configured: dict[str, str | None], landing_zone: LandingZoneRepository):
        self._configured = configured
        self._landing_zone = landing_zone

    def resolve(self, provider: str = DEFAULT_PROVIDER) -> str | None:
        if self._configured.get(provider):
            return self._configured[provider]
        record = self._landing_zone.latest_applied(provider)
        if record is None:
            return None
        toolkit = ProviderRegistry.default().get(provider).landing_zone()
        backup = toolkit.namer(LandingZoneAnswers.model_validate(record.answers)).unit(
            toolkit.units.infrastructure["backup"]).name
        return (record.accounts or {}).get(backup)
