from abc import ABC, abstractmethod
from collections.abc import Callable

from app.synth.request import ProjectRequest


class ChangeRule(ABC):
    """One thing a change to a provisioned project may not do (§21.8 C1). Add rules to ChangeRules."""

    @abstractmethod
    def problems(self, current: ProjectRequest, proposed: ProjectRequest) -> list[str]:
        ...


class LockedFieldRule(ChangeRule):
    def __init__(self, label: str, value: Callable[[ProjectRequest], object]):
        self._label = label
        self._value = value

    def problems(self, current, proposed):
        return [] if self._value(current) == self._value(proposed) else [f"The {self._label} cannot change."]


class EnvironmentsAddOnlyRule(ChangeRule):
    def problems(self, current, proposed):
        removed = [environment for environment in current.environments if environment not in proposed.environments]
        if not removed:
            return []
        return [f"Environments can only be added; removing {', '.join(removed)} is not supported yet."]


class SomethingChangedRule(ChangeRule):
    def problems(self, current, proposed):
        return [] if _comparable(current) != _comparable(proposed) else ["Nothing changed."]


class ChangeRules:
    def __init__(self, rules: list[ChangeRule]):
        self._rules = rules

    @classmethod
    def default(cls) -> "ChangeRules":
        return cls([
            LockedFieldRule("project name", lambda request: request.project_name),
            LockedFieldRule("portfolio", lambda request: request.ownership.portfolio_id),
            LockedFieldRule("product", lambda request: request.ownership.product_id),
            LockedFieldRule("data classification", lambda request: request.ownership.data_classification),
            LockedFieldRule("resilience mode and regions", lambda request: request.resilience),
            EnvironmentsAddOnlyRule(),
            SomethingChangedRule(),
        ])

    def problems(self, current: ProjectRequest, proposed: ProjectRequest) -> list[str]:
        return [problem for rule in self._rules for problem in rule.problems(current, proposed)]


def _comparable(request: ProjectRequest) -> dict:
    document = request.model_dump(mode="json")
    return {**document, "environments": sorted(document["environments"])}
