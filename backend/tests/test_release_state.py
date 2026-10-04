import pytest

from app.errors import ConflictError
from app.releases.state import InvalidTransitionError, ReleaseState, ReleaseStateMachine

MACHINE = ReleaseStateMachine()


@pytest.mark.parametrize(("current", "target"), [
    ("planned", "gate_failed"), ("planned", "override_requested"), ("planned", "awaiting_approval"),
    ("planned", "deploying"), ("override_requested", "awaiting_approval"), ("override_requested", "deploying"),
    ("override_requested", "rejected"), ("awaiting_approval", "deploying"), ("awaiting_approval", "rejected"),
    ("awaiting_approval", "superseded"), ("deploying", "deployed"), ("deploying", "rolled_back")])
def test_allowed_transitions(current, target):
    assert MACHINE.check(current, target) is None


def test_disallowed_transition():
    with pytest.raises(InvalidTransitionError, match="Cannot move a release from deployed to deploying."):
        MACHINE.check("deployed", "deploying")


def test_invalid_transition_is_a_conflict():
    assert issubclass(InvalidTransitionError, ConflictError)


def test_pending_states():
    assert ReleaseState.PENDING == frozenset({"awaiting_approval", "override_requested"})
