import uuid

import pytest
from sqlalchemy import select

from app.db import models
from app.provisioning.queue import IdempotencyConflictError, JobQueue, JobState
from tests.factories import request_dict


def enqueue(session, key: str = "k1", project: str = "demo-app") -> models.Job:
    return JobQueue(session).enqueue(project_name=project, request_id=key,
                                     payload=request_dict(project_name=project))


def test_enqueued_job_is_queued(session):
    assert enqueue(session).state == JobState.QUEUED


def test_enqueue_is_idempotent(session):
    assert enqueue(session).id == enqueue(session).id


def test_same_key_with_different_payload_conflicts(session):
    enqueue(session)
    with pytest.raises(IdempotencyConflictError):
        enqueue(session, project="other-app")


def test_claim_marks_job_running(session):
    enqueue(session)
    assert JobQueue(session).claim_next().state == JobState.RUNNING


def test_claim_returns_none_when_empty(session):
    assert JobQueue(session).claim_next() is None


def test_claimed_job_is_not_claimed_twice(session):
    enqueue(session)
    JobQueue(session).claim_next()
    assert JobQueue(session).claim_next() is None


def test_locked_job_is_skipped(session_factory):
    with session_factory() as setup:
        enqueue(setup)
    with session_factory() as holder, session_factory() as claimer:
        holder.execute(select(models.Job).with_for_update())
        assert JobQueue(claimer).claim_next() is None
        holder.rollback()


def test_steps_are_numbered(session):
    job = enqueue(session)
    queue = JobQueue(session)
    queue.record_step(job, "create_repo", "succeeded")
    queue.record_step(job, "commit", "failed", "boom")
    assert [(step.sequence, step.name, step.detail) for step in queue.steps(job)] == [
        (1, "create_repo", ""), (2, "commit", "boom")]


def test_finish_sets_state_and_error(session):
    job = enqueue(session)
    JobQueue(session).finish(job, JobState.FAILED_ROLLED_BACK, "boom")
    assert (job.state, job.error) == (JobState.FAILED_ROLLED_BACK, "boom")


def test_get_job(session):
    job = enqueue(session)
    assert JobQueue(session).get(job.id) is job


def test_get_unknown_job(session):
    assert JobQueue(session).get(uuid.uuid4()) is None
