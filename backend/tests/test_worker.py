from app.adapters.factory import AdapterFactory
from app.db import models
from app.provisioning.queue import JobQueue, JobState
from app.provisioning.worker import Worker, WorkerCommand
from app.seed import ReferenceDataSeeder
from tests.factories import request_dict


def build_worker(session_factory, settings) -> Worker:
    factory = AdapterFactory()
    return Worker(session_factory, factory.github(settings), factory.aws(settings), settings.github_owner)


def enqueue_project(session_factory) -> models.Job:
    payload = request_dict()
    with session_factory() as session:
        ReferenceDataSeeder(session).seed()
        session.add(models.Project(name="invoice-ingest", portfolio_id="pf-payments", product_id="pr-invoicing",
                                   resilience_mode="single", status="provisioning", request=payload))
        return JobQueue(session).enqueue(project_name="invoice-ingest", request_id="k1", payload=payload)


def test_no_job_means_nothing_processed(session_factory, settings):
    assert build_worker(session_factory, settings).process_one() is False


def test_worker_processes_a_job(session_factory, settings):
    job = enqueue_project(session_factory)
    build_worker(session_factory, settings).process_one()
    with session_factory() as session:
        assert session.get(models.Job, job.id).state == JobState.SUCCEEDED


def test_command_sleeps_when_idle(session_factory, settings):
    pauses = []
    WorkerCommand(settings, sleep=pauses.append).run(max_iterations=2)
    assert pauses == [0, 0]


def test_command_does_not_sleep_after_work(session_factory, settings):
    enqueue_project(session_factory)
    pauses = []
    WorkerCommand(settings, sleep=pauses.append).run(max_iterations=1)
    assert pauses == []
