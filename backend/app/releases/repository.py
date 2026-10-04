import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models
from app.releases.state import ReleaseState


class ReleaseRepository:
    def __init__(self, session: Session):
        self._session = session

    def add(self, release: models.Release) -> None:
        self._session.add(release)
        self._session.flush()

    def get(self, release_id: uuid.UUID) -> models.Release | None:
        return self._session.get(models.Release, release_id)

    def latest_for(self, project_name: str, environment_id: str) -> models.Release | None:
        return self._session.scalars(self._for(project_name, environment_id)
                                     .order_by(models.Release.created_at.desc()).limit(1)).first()

    def pending_for(self, project_name: str, environment_id: str) -> list[models.Release]:
        return list(self._session.scalars(self._for(project_name, environment_id)
                                          .where(models.Release.state.in_(ReleaseState.PENDING))))

    def last_deployed_artifact(self, project_name: str, environment_id: str) -> str | None:
        return self._session.scalar(
            select(models.Release.artifact_digest)
            .where(models.Release.project_name == project_name, models.Release.environment_id == environment_id,
                   models.Release.state == ReleaseState.DEPLOYED)
            .order_by(models.Release.created_at.desc()).limit(1))

    def in_states(self, states: list[str]) -> list[models.Release]:
        return list(self._session.scalars(select(models.Release).where(models.Release.state.in_(states))
                                          .order_by(models.Release.created_at)))

    def for_project(self, project_name: str | None) -> list[models.Release]:
        query = select(models.Release).order_by(models.Release.created_at.desc())
        if project_name is not None:
            query = query.where(models.Release.project_name == project_name)
        return list(self._session.scalars(query))

    def add_decision(self, decision: models.ReleaseDecision) -> None:
        self._session.add(decision)

    def decisions(self, release: models.Release) -> list[models.ReleaseDecision]:
        return list(self._session.scalars(select(models.ReleaseDecision)
                                          .where(models.ReleaseDecision.release_id == release.id)
                                          .order_by(models.ReleaseDecision.id)))

    def commit(self) -> None:
        self._session.commit()

    def _for(self, project_name: str, environment_id: str):
        return select(models.Release).where(models.Release.project_name == project_name,
                                            models.Release.environment_id == environment_id)
