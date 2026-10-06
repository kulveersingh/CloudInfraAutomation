import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import models
from app.landing_zone.states import DesignStatus
from app.providers.base import DEFAULT_PROVIDER


class LandingZoneRepository:
    def __init__(self, session: Session):
        self._session = session

    def all(self, provider: str | None = None) -> list[models.LandingZoneDesignRecord]:
        query = select(models.LandingZoneDesignRecord).order_by(models.LandingZoneDesignRecord.version.desc())
        if provider is not None:
            query = query.where(models.LandingZoneDesignRecord.provider == provider)
        return list(self._session.scalars(query))

    def get(self, design_id: uuid.UUID) -> models.LandingZoneDesignRecord | None:
        return self._session.get(models.LandingZoneDesignRecord, design_id)

    def latest_applied(self, provider: str = DEFAULT_PROVIDER) -> models.LandingZoneDesignRecord | None:
        """A cloud's applied landing zone: each cloud has its own (§22.7 MC4)."""
        record = models.LandingZoneDesignRecord
        return self._session.scalar(select(record).where(record.status == DesignStatus.APPLIED,
                                                         record.provider == provider)
                                    .order_by(record.version.desc()).limit(1))

    def next_version(self, provider: str = DEFAULT_PROVIDER) -> int:
        record = models.LandingZoneDesignRecord
        return (self._session.scalar(select(func.max(record.version)).where(record.provider == provider)) or 0) + 1

    def add(self, record: models.LandingZoneDesignRecord) -> None:
        self._session.add(record)

    def commit(self) -> None:
        self._session.commit()
