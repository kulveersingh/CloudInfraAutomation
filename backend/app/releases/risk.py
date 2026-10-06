from abc import ABC, abstractmethod

from app.releases.plan import ChangeSpec


class ResourceClassifier(ABC):
    """A provider's view of its plan rows: which resource types hold data, and which change permissions."""

    @abstractmethod
    def is_stateful(self, resource_type: str) -> bool:
        ...

    @abstractmethod
    def is_permission(self, resource_type: str) -> bool:
        ...

    @abstractmethod
    def rows(self, document: dict) -> list[tuple[str, str]]:
        """(address, type) of each resource of a generated document: the rows a first plan of it would have."""

    def rules(self) -> list["RiskRule"]:
        """Rules this provider's plans need besides the common ones."""
        return []


class RiskLevel:
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    ORDER = (LOW, MEDIUM, HIGH)

    @classmethod
    def highest(cls, levels: list[str]) -> str:
        return max(levels, key=cls.ORDER.index, default=cls.LOW)


class RiskRule(ABC):
    """Rates one change; returns a RiskLevel or None when the rule does not apply."""

    @abstractmethod
    def risk_of(self, change: ChangeSpec) -> str | None:
        ...


class StatefulDestructionRule(RiskRule):
    def __init__(self, resources: ResourceClassifier):
        self._resources = resources

    def risk_of(self, change):
        destroys = change.action == "Remove" or change.replacement
        return RiskLevel.HIGH if self._resources.is_stateful(change.resource_type) and destroys else None


class PermissionChangeRule(RiskRule):
    def __init__(self, resources: ResourceClassifier):
        self._resources = resources

    def risk_of(self, change):
        return RiskLevel.MEDIUM if self._resources.is_permission(change.resource_type) else None


class ResourceRemovalRule(RiskRule):
    def risk_of(self, change):
        return RiskLevel.MEDIUM if change.action == "Remove" else None


class ChangeRiskClassifier:
    def __init__(self, rules: list[RiskRule]):
        self._rules = rules

    @classmethod
    def for_resources(cls, resources: ResourceClassifier) -> "ChangeRiskClassifier":
        return cls([StatefulDestructionRule(resources), PermissionChangeRule(resources), ResourceRemovalRule(),
                    *resources.rules()])

    def risk_of(self, change: ChangeSpec) -> str:
        return RiskLevel.highest([level for rule in self._rules if (level := rule.risk_of(change)) is not None])

    def overall(self, changes: list[ChangeSpec]) -> str:
        return RiskLevel.highest([self.risk_of(change) for change in changes])

    def classify(self, changes: list[ChangeSpec]) -> list[dict]:
        return [{**change.model_dump(), "risk": self.risk_of(change)} for change in changes]
