import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models
from app.teardown.states import RestoreState, TeardownState


class TeardownRepository:
    def __init__(self, session: Session):
        self._session = session

    def add(self, teardown: models.Teardown, environments: list[models.TeardownEnvironment]) -> None:
        self._session.add(teardown)
        self._session.flush()
        for environment in environments:
            environment.teardown_id = teardown.id
            self._session.add(environment)
        self._session.flush()

    def get(self, teardown_id: uuid.UUID) -> models.Teardown | None:
        return self._session.get(models.Teardown, teardown_id)

    def all(self) -> list[models.Teardown]:
        return list(self._session.scalars(select(models.Teardown).order_by(models.Teardown.created_at.desc())))

    def for_project(self, project_name: str) -> list[models.Teardown]:
        return list(self._session.scalars(select(models.Teardown).where(models.Teardown.project_name == project_name)
                                          .order_by(models.Teardown.created_at.desc())))

    def active(self, project_name: str) -> models.Teardown | None:
        """A teardown still running, or a restore requested or running: either blocks other work on the project."""
        return next((teardown for teardown in self.for_project(project_name)
                     if teardown.state == TeardownState.IN_PROGRESS
                     or teardown.restore_state in RestoreState.ACTIVE), None)

    def environments(self, teardown: models.Teardown) -> list[models.TeardownEnvironment]:
        return list(self._session.scalars(select(models.TeardownEnvironment)
                                          .where(models.TeardownEnvironment.teardown_id == teardown.id)
                                          .order_by(models.TeardownEnvironment.position)))

    def environment(self, environment_id: uuid.UUID) -> models.TeardownEnvironment | None:
        return self._session.get(models.TeardownEnvironment, environment_id)

    def recovery_points(self, environment: models.TeardownEnvironment) -> list[models.TeardownRecoveryPoint]:
        return list(self._session.scalars(select(models.TeardownRecoveryPoint).where(
            models.TeardownRecoveryPoint.teardown_environment_id == environment.id)
            .order_by(models.TeardownRecoveryPoint.id)))

    def add_recovery_point(self, point: models.TeardownRecoveryPoint) -> None:
        self._session.add(point)
        self._session.flush()

    def commit(self) -> None:
        self._session.commit()

    def rollback(self) -> None:
        self._session.rollback()
