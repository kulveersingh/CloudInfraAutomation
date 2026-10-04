from abc import ABC, abstractmethod

from app.releases.plan import ChangeSpec

STATEFUL_TYPES = frozenset({
    "AWS::S3::Bucket", "AWS::DynamoDB::Table", "AWS::DynamoDB::GlobalTable", "AWS::RDS::DBCluster",
    "AWS::RDS::DBInstance", "AWS::EFS::FileSystem", "AWS::Kinesis::Stream", "AWS::SQS::Queue",
    "AWS::OpenSearchService::Domain", "AWS::ElastiCache::ReplicationGroup", "AWS::Neptune::DBCluster",
    "AWS::DocDB::DBCluster", "AWS::KMS::Key", "AWS::SecretsManager::Secret",
})


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
    def risk_of(self, change):
        destroys = change.action == "Remove" or change.replacement
        return RiskLevel.HIGH if change.resource_type in STATEFUL_TYPES and destroys else None


class PermissionChangeRule(RiskRule):
    def risk_of(self, change):
        resource_type = change.resource_type
        permission = (resource_type.startswith("AWS::IAM::") or resource_type.endswith("Policy")
                      or resource_type == "AWS::Lambda::Permission")
        return RiskLevel.MEDIUM if permission else None


class ResourceRemovalRule(RiskRule):
    def risk_of(self, change):
        return RiskLevel.MEDIUM if change.action == "Remove" else None


class ChangeRiskClassifier:
    def __init__(self, rules: list[RiskRule]):
        self._rules = rules

    @classmethod
    def default(cls) -> "ChangeRiskClassifier":
        return cls([StatefulDestructionRule(), PermissionChangeRule(), ResourceRemovalRule()])

    def risk_of(self, change: ChangeSpec) -> str:
        return RiskLevel.highest([level for rule in self._rules if (level := rule.risk_of(change)) is not None])

    def overall(self, changes: list[ChangeSpec]) -> str:
        return RiskLevel.highest([self.risk_of(change) for change in changes])

    def classify(self, changes: list[ChangeSpec]) -> list[dict]:
        return [{**change.model_dump(), "risk": self.risk_of(change)} for change in changes]
