class JobState:
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED_ROLLED_BACK = "failed_rolled_back"
    FAILED_NEEDS_ATTENTION = "failed_needs_attention"


class StepState:
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    COMPENSATED = "compensated"
    COMPENSATION_FAILED = "compensation_failed"


class ProjectStatus:
    PROVISIONING = "provisioning"
    ACTIVE = "active"
    FAILED = "failed"
    DECOMMISSIONED = "decommissioned"

    @classmethod
    def for_job_state(cls, job_state: str) -> str:
        return cls.ACTIVE if job_state == JobState.SUCCEEDED else cls.FAILED
