from typing import ClassVar

from app.errors import ConflictError


class ReleaseState:
    PLANNED = "planned"
    GATE_FAILED = "gate_failed"
    OVERRIDE_REQUESTED = "override_requested"
    AWAITING_APPROVAL = "awaiting_approval"
    DEPLOYING = "deploying"
    DEPLOYED = "deployed"
    ROLLED_BACK = "rolled_back"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"
    PENDING = frozenset({AWAITING_APPROVAL, OVERRIDE_REQUESTED})


class InvalidTransitionError(ConflictError):
    pass


class ReleaseStateMachine:
    """The only allowed moves between release states."""

    TRANSITIONS: ClassVar[dict[str, frozenset[str]]] = {
        ReleaseState.PLANNED: frozenset({ReleaseState.GATE_FAILED, ReleaseState.OVERRIDE_REQUESTED,
                                         ReleaseState.AWAITING_APPROVAL, ReleaseState.DEPLOYING}),
        ReleaseState.OVERRIDE_REQUESTED: frozenset({ReleaseState.AWAITING_APPROVAL, ReleaseState.DEPLOYING,
                                                    ReleaseState.REJECTED, ReleaseState.SUPERSEDED}),
        ReleaseState.AWAITING_APPROVAL: frozenset({ReleaseState.DEPLOYING, ReleaseState.REJECTED,
                                                   ReleaseState.SUPERSEDED}),
        ReleaseState.DEPLOYING: frozenset({ReleaseState.DEPLOYED, ReleaseState.ROLLED_BACK}),
    }

    def check(self, current: str, target: str) -> None:
        if target not in self.TRANSITIONS.get(current, frozenset()):
            raise InvalidTransitionError(f"Cannot move a release from {current} to {target}.")
