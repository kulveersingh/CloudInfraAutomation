import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import models
from app.landing_zone.states import DesignStatus


class LandingZoneRepository:
    def __init__(self, session: Session):
        self._session = session

    def all(self) -> list[models.LandingZoneDesignRecord]:
        return list(self._session.scalars(select(models.LandingZoneDesignRecord)
                                          .order_by(models.LandingZoneDesignRecord.version.desc())))

    def get(self, design_id: uuid.UUID) -> models.LandingZoneDesignRecord | None:
        return self._session.get(models.LandingZoneDesignRecord, design_id)

    def latest_applied(self) -> models.LandingZoneDesignRecord | None:
        return self._session.scalar(select(models.LandingZoneDesignRecord)
                                    .where(models.LandingZoneDesignRecord.status == DesignStatus.APPLIED)
                                    .order_by(models.LandingZoneDesignRecord.version.desc()).limit(1))

    def next_version(self) -> int:
        return (self._session.scalar(select(func.max(models.LandingZoneDesignRecord.version))) or 0) + 1

    def add(self, record: models.LandingZoneDesignRecord) -> None:
        self._session.add(record)

    def commit(self) -> None:
        self._session.commit()
