from app.landing_zone.repository import LandingZoneRepository


class BackupAccountResolver:
    """The central Backup account: configured explicitly, or the applied landing zone's `<org>-backup` account."""

    def __init__(self, configured: str | None, landing_zone: LandingZoneRepository):
        self._configured = configured
        self._landing_zone = landing_zone

    def resolve(self) -> str | None:
        if self._configured:
            return self._configured
        record = self._landing_zone.latest_applied()
        if record is None:
            return None
        return (record.accounts or {}).get(f"{record.answers['organization_name']}-backup")
