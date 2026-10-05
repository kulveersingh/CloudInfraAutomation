import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models


class ChangeState:
    QUEUED = "queued"
    OPEN = "open"
    MERGED = "merged"
    CLOSED = "closed"
    FAILED = "failed"

    ACTIVE = (QUEUED, OPEN)


class ProjectChangeRepository:
    def __init__(self, session: Session):
        self._session = session

    def get(self, change_id: uuid.UUID) -> models.ProjectChange | None:
        return self._session.get(models.ProjectChange, change_id)

    def for_project(self, project_name: str) -> list[models.ProjectChange]:
        return list(self._session.scalars(select(models.ProjectChange)
                                          .where(models.ProjectChange.project_name == project_name)
                                          .order_by(models.ProjectChange.created_at.desc())))

    def active(self, project_name: str) -> models.ProjectChange | None:
        return self._session.scalar(select(models.ProjectChange).where(
            models.ProjectChange.project_name == project_name, models.ProjectChange.state.in_(ChangeState.ACTIVE)))

    def add(self, change: models.ProjectChange) -> None:
        self._session.add(change)
        self._session.flush()

    def commit(self) -> None:
        self._session.commit()
