import uuid

from app.db import models
from app.provisioning.queue import JobQueue
from app.teardown.policy import REVIEWER
from app.teardown.repository import TeardownRepository
from app.teardown.states import EnvironmentState

TEARDOWN_JOB = "teardown"


class TeardownScheduler:
    """Starts approved environments when it is their turn: STAGE and PROD only after every other environment of the
    teardown is torn down, and in pipeline order, so PROD goes last (§21.9.3)."""

    def __init__(self, teardowns: TeardownRepository, queue: JobQueue):
        self._teardowns = teardowns
        self._queue = queue

    def start_ready(self, teardown: models.Teardown) -> None:
        environments = self._teardowns.environments(teardown)
        for environment in environments:
            if environment.state == EnvironmentState.APPROVED and self._has_turn(environment, environments):
                self.enqueue(teardown, environment)

    def enqueue(self, teardown: models.Teardown, environment: models.TeardownEnvironment) -> None:
        job = self._queue.enqueue(teardown.project_name, f"teardown-{uuid.uuid4()}",
                                  {"teardown_environment_id": str(environment.id), "provider": teardown.provider},
                                  kind=TEARDOWN_JOB)
        environment.job_id, environment.state, environment.error = job.id, EnvironmentState.QUEUED, None

    def _has_turn(self, environment: models.TeardownEnvironment,
                  environments: list[models.TeardownEnvironment]) -> bool:
        if environment.approver_role == REVIEWER:
            return True
        before = [other for other in environments
                  if other.approver_role == REVIEWER or other.position < environment.position]
        return all(other.state == EnvironmentState.COMPLETED for other in before)
