from app.landing_zone.repository import LandingZoneRepository
from app.providers.base import DEFAULT_PROVIDER


class BackupAccountResolver:
    """The central backup account of each cloud: configured explicitly, or the applied landing zone's `<org>-backup`
    account. Landing zones are on AWS until MC-3, so other clouds use only their configured account."""

    def __init__(self, configured: dict[str, str | None], landing_zone: LandingZoneRepository,
                 landing_zone_provider: str = DEFAULT_PROVIDER):
        self._configured = configured
        self._landing_zone = landing_zone
        self._landing_zone_provider = landing_zone_provider

    def resolve(self, provider: str = DEFAULT_PROVIDER) -> str | None:
        if self._configured.get(provider):
            return self._configured[provider]
        if provider != self._landing_zone_provider:
            return None
        record = self._landing_zone.latest_applied()
        if record is None:
            return None
        return (record.accounts or {}).get(f"{record.answers['organization_name']}-backup")
