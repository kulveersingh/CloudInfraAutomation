from app.db import models
from app.teardown.repository import TeardownRepository


class TeardownRecords:
    """The teardown record (§21.9.4), the same in the API and in teardowns/{id}.json in the repository."""

    def __init__(self, teardowns: TeardownRepository):
        self._teardowns = teardowns

    def record(self, teardown: models.Teardown) -> dict:
        """What a restore needs. Only fields that do not change after a commit, so read-back stays verified."""
        return {"id": str(teardown.id), "project_name": teardown.project_name, "scope": teardown.scope,
                "state": teardown.state, "requested_by": teardown.requested_by,
                "base_revision": teardown.base_revision, "base_request": teardown.base_request,
                "base_commit": teardown.base_commit, "created_at": teardown.created_at.isoformat(),
                "environments": [self._environment(environment)
                                 for environment in self._teardowns.environments(teardown)],
                "restore": self._restore(teardown)}

    def describe(self, teardown: models.Teardown) -> dict:
        """The record plus the platform's working state: jobs and errors."""
        record = self.record(teardown)
        environments = self._teardowns.environments(teardown)
        record["environments"] = [{**item, "job_id": _text(environment.job_id), "error": environment.error}
                                  for item, environment in zip(record["environments"], environments, strict=True)]
        if record["restore"] is not None:
            record["restore"]["job_id"] = _text(teardown.restore_job_id)
        return record

    def committed(self, teardown: models.Teardown) -> bool:
        """Whether any environment's removal reached the repository, so the record belongs there too."""
        return any(environment.revision is not None for environment in self._teardowns.environments(teardown))

    def _environment(self, environment: models.TeardownEnvironment) -> dict:
        return {"environment": environment.environment, "state": environment.state,
                "approver_role": environment.approver_role, "account_id": environment.account_id,
                "regions": environment.regions, "decided_by": environment.decided_by,
                "decision_comment": environment.decision_comment, "revision": environment.revision,
                "recovery_points": [_point(point) for point in self._teardowns.recovery_points(environment)]}

    def _restore(self, teardown: models.Teardown) -> dict | None:
        if teardown.restore_state is None:
            return None
        return {"state": teardown.restore_state, "requested_by": teardown.restore_requested_by,
                "decided_by": teardown.restore_decided_by}


def _point(point: models.TeardownRecoveryPoint) -> dict:
    return {"service_id": point.service_id, "logical_id": point.logical_id, "resource_type": point.resource_type,
            "physical_name": point.physical_name, "region": point.region, "account_id": point.account_id,
            "recovery_point_arn": point.recovery_point_arn, "vault": point.vault,
            "completed_at": point.completed_at.isoformat(), "locked_until": point.locked_until.isoformat()}


def _text(value) -> str | None:
    return str(value) if value is not None else None
