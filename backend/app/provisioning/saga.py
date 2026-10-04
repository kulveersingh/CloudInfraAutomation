from collections.abc import Callable
from dataclasses import dataclass

from app.provisioning.states import JobState, StepState
from app.provisioning.steps import ProvisioningStep

StepReporter = Callable[[str, str, str], None]


@dataclass(frozen=True)
class SagaOutcome:
    state: str
    error: str | None = None


class Saga:
    """Runs steps in order; on failure, undoes completed steps in reverse order."""

    def __init__(self, steps: list[ProvisioningStep], report: StepReporter):
        self._steps = steps
        self._report = report

    def run(self, context) -> SagaOutcome:
        completed: list[ProvisioningStep] = []
        for step in self._steps:
            try:
                step.execute(context)
            except Exception as error:  # any failure must trigger compensation
                self._report(step.name, StepState.FAILED, str(error))
                return self._roll_back(completed, context, str(error))
            self._report(step.name, StepState.SUCCEEDED, "")
            completed.append(step)
        return SagaOutcome(JobState.SUCCEEDED)

    def _roll_back(self, completed: list[ProvisioningStep], context, error: str) -> SagaOutcome:
        results = [self._compensate(step, context) for step in reversed(completed)]
        state = JobState.FAILED_ROLLED_BACK if all(results) else JobState.FAILED_NEEDS_ATTENTION
        return SagaOutcome(state, error)

    def _compensate(self, step: ProvisioningStep, context) -> bool:
        try:
            step.compensate(context)
        except Exception as error:  # report and continue undoing the remaining steps
            self._report(step.name, StepState.COMPENSATION_FAILED, str(error))
            return False
        self._report(step.name, StepState.COMPENSATED, "")
        return True
