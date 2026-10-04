from app.provisioning.saga import Saga, SagaOutcome
from app.provisioning.steps import ProvisioningStep


class RecordingStep(ProvisioningStep):
    def __init__(self, name: str, log: list, fail: bool = False, fail_compensation: bool = False):
        self.name = name
        self.log = log
        self.fail = fail
        self.fail_compensation = fail_compensation

    def execute(self, context) -> None:
        self.log.append(f"do:{self.name}")
        if self.fail:
            raise RuntimeError(f"{self.name} failed")

    def compensate(self, context) -> None:
        self.log.append(f"undo:{self.name}")
        if self.fail_compensation:
            raise RuntimeError(f"undo {self.name} failed")


class SilentStep(ProvisioningStep):
    name = "silent"

    def execute(self, context) -> None:
        return None


def run(steps: list, events: list | None = None) -> SagaOutcome:
    def record(name: str, state: str, detail: str) -> None:
        if events is not None:
            events.append((name, state))

    return Saga(steps, record).run(context=None)


def test_all_steps_succeed():
    log = []
    assert run([RecordingStep("a", log), RecordingStep("b", log)]).state == "succeeded"


def test_steps_run_in_order():
    log = []
    run([RecordingStep("a", log), RecordingStep("b", log)])
    assert log == ["do:a", "do:b"]


def test_failure_compensates_completed_steps_in_reverse():
    log = []
    run([RecordingStep("a", log), RecordingStep("b", log), RecordingStep("c", log, fail=True)])
    assert log == ["do:a", "do:b", "do:c", "undo:b", "undo:a"]


def test_failure_outcome_is_rolled_back():
    outcome = run([RecordingStep("a", []), RecordingStep("b", [], fail=True)])
    assert (outcome.state, outcome.error) == ("failed_rolled_back", "b failed")


def test_failed_compensation_needs_attention():
    log = []
    outcome = run([RecordingStep("a", log, fail_compensation=True), RecordingStep("b", log, fail=True)])
    assert outcome.state == "failed_needs_attention"


def test_events_are_reported():
    events = []
    run([RecordingStep("a", []), RecordingStep("b", [], fail=True)], events)
    assert events == [("a", "succeeded"), ("b", "failed"), ("a", "compensated")]


def test_failed_compensation_is_reported():
    events = []
    run([RecordingStep("a", [], fail_compensation=True), RecordingStep("b", [], fail=True)], events)
    assert events[-1] == ("a", "compensation_failed")


def test_default_compensation_does_nothing():
    assert SilentStep().compensate(context=None) is None
