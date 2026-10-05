import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models
from app.errors import ConflictError
from app.provisioning.states import JobState

__all__ = ["IdempotencyConflictError", "JobQueue", "JobState"]


class IdempotencyConflictError(ConflictError):
    pass


class JobQueue:
    """Provisioning jobs in PostgreSQL; workers claim them with FOR UPDATE SKIP LOCKED."""

    def __init__(self, session: Session):
        self._session = session

    def enqueue(self, project_name: str, request_id: str, payload: dict, kind: str = "provision",
                change_id: uuid.UUID | None = None) -> models.Job:
        existing = self.by_request_id(request_id)
        if existing is not None:
            self._ensure_same_request(existing, project_name, payload)
            return existing
        job = models.Job(project_name=project_name, request_id=request_id, payload=payload, kind=kind,
                         change_id=change_id, state=JobState.QUEUED)
        self._session.add(job)
        self._session.commit()
        return job

    def by_request_id(self, request_id: str) -> models.Job | None:
        return self._session.scalar(select(models.Job).where(models.Job.request_id == request_id))

    def for_change(self, change_id: uuid.UUID) -> models.Job | None:
        return self._session.scalar(select(models.Job).where(models.Job.change_id == change_id))

    def get(self, job_id: uuid.UUID) -> models.Job | None:
        return self._session.get(models.Job, job_id)

    def claim_next(self) -> models.Job | None:
        job = self._session.scalars(
            select(models.Job).where(models.Job.state == JobState.QUEUED).order_by(models.Job.created_at)
            .limit(1).with_for_update(skip_locked=True)).first()
        if job is not None:
            job.state = JobState.RUNNING
            self._session.commit()
        return job

    def record_step(self, job: models.Job, name: str, state: str, detail: str = "") -> None:
        sequence = len(self.steps(job)) + 1
        self._session.add(models.JobStep(job_id=job.id, sequence=sequence, name=name, state=state, detail=detail))
        self._session.commit()

    def steps(self, job: models.Job) -> list[models.JobStep]:
        return list(self._session.scalars(
            select(models.JobStep).where(models.JobStep.job_id == job.id).order_by(models.JobStep.sequence)))

    def finish(self, job: models.Job, state: str, error: str | None = None) -> None:
        job.state = state
        job.error = error
        self._session.commit()

    def _ensure_same_request(self, job: models.Job, project_name: str, payload: dict) -> None:
        if (job.project_name, job.payload) != (project_name, payload):
            raise IdempotencyConflictError(f"Idempotency key '{job.request_id}' was used for a different request.")
