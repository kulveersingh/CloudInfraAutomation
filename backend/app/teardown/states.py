class TeardownScope:
    ENVIRONMENT = "environment"
    PROJECT = "project"


class TeardownState:
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    PARTIALLY_COMPLETED = "partially_completed"
    REJECTED = "rejected"


class EnvironmentState:
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"  # approved, waiting for its turn (STAGE and PROD go after the other environments)
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    FAILED = "failed_needs_attention"

    UNSETTLED = frozenset({PENDING_APPROVAL, APPROVED, QUEUED, RUNNING, FAILED})
    WAITING = frozenset({PENDING_APPROVAL, APPROVED})


class RestoreState:
    REQUESTED = "requested"
    QUEUED = "queued"
    RUNNING = "running"
    RESTORED = "restored"
    REJECTED = "rejected"
    FAILED = "failed"

    ACTIVE = frozenset({REQUESTED, QUEUED, RUNNING})


def overall_state(states: list[str]) -> str:
    if any(state in EnvironmentState.UNSETTLED for state in states):
        return TeardownState.IN_PROGRESS
    if all(state == EnvironmentState.COMPLETED for state in states):
        return TeardownState.COMPLETED
    if EnvironmentState.COMPLETED in states:
        return TeardownState.PARTIALLY_COMPLETED
    return TeardownState.REJECTED
