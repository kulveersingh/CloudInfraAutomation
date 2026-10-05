import itertools
import time
from collections.abc import Callable

from sqlalchemy.orm import sessionmaker

from app.adapters.factory import AdapterFactory
from app.adapters.ports import AwsPort, GitHubPort
from app.config import Settings
from app.db.database import Database
from app.provisioning.change_runner import ChangeJobRunner
from app.provisioning.queue import JobQueue
from app.provisioning.runner import JobRunner
from app.readback.manifest import ManifestSigner
from app.teardown.jobs import RestoreJobRunner, TeardownJobRunner

RUNNERS = {"provision": JobRunner, "change": ChangeJobRunner, "teardown": TeardownJobRunner,
           "restore": RestoreJobRunner}


class Worker:
    """Claims and runs one queued job at a time. Runs as its own ECS service on AWS."""

    def __init__(self, session_factory: sessionmaker, github: GitHubPort, aws: AwsPort, owner: str,
                 signer: ManifestSigner):
        self._session_factory = session_factory
        self._github = github
        self._aws = aws
        self._owner = owner
        self._signer = signer

    def process_one(self) -> bool:
        with self._session_factory() as session:
            job = JobQueue(session).claim_next()
            if job is None:
                return False
            RUNNERS[job.kind].for_session(session, self._github, self._aws, self._owner, self._signer).run(job)
            return True


class WorkerCommand:
    def __init__(self, settings: Settings, sleep: Callable[[float], None] = time.sleep):
        self._settings = settings
        self._sleep = sleep

    def run(self, max_iterations: int | None = None) -> None:
        adapters = AdapterFactory()
        worker = Worker(Database(self._settings.sqlalchemy_url()).session_factory, adapters.github(self._settings),
                        adapters.aws(self._settings), self._settings.github_owner,
                        ManifestSigner.from_settings(self._settings))
        for _ in self._iterations(max_iterations):
            if not worker.process_one():
                self._sleep(self._settings.worker_poll_seconds)

    def _iterations(self, max_iterations: int | None):
        return itertools.count() if max_iterations is None else range(max_iterations)


if __name__ == "__main__":
    WorkerCommand(Settings()).run()
