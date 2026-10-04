from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models


class ProjectRepository:
    def __init__(self, session: Session):
        self._session = session

    def get(self, name: str) -> models.Project | None:
        return self._session.get(models.Project, name)

    def add(self, project: models.Project) -> None:
        self._session.add(project)

    def all(self) -> list[models.Project]:
        return list(self._session.scalars(select(models.Project).order_by(models.Project.name)))

    def set_status(self, name: str, status: str, commit_sha: str | None = None) -> None:
        project = self.get(name)
        project.status = status
        if commit_sha is not None:
            project.commit_sha = commit_sha
        self._session.commit()
