from app.db import models
from app.landing_zone.repository import LandingZoneRepository
from app.teardown.backup_account import BackupAccountResolver


def record(status: str, version: int, accounts: dict | None) -> models.LandingZoneDesignRecord:
    return models.LandingZoneDesignRecord(version=version, answers={"organization_name": "acme"}, edits=[],
                                          status=status, created_by="alex", accounts=accounts)


def test_configured_account_wins(session):
    assert BackupAccountResolver("999999999999", LandingZoneRepository(session)).resolve() == "999999999999"


def test_without_a_landing_zone_there_is_none(session):
    assert BackupAccountResolver(None, LandingZoneRepository(session)).resolve() is None


def test_the_applied_landing_zone_backup_account_is_used(session):
    session.add(record("applied", 1, {"acme-backup": "123456789012", "acme-network": "210987654321"}))
    session.commit()
    assert BackupAccountResolver(None, LandingZoneRepository(session)).resolve() == "123456789012"


def test_a_landing_zone_without_a_backup_account_has_none(session):
    session.add(record("applied", 1, None))
    session.commit()
    assert BackupAccountResolver(None, LandingZoneRepository(session)).resolve() is None
