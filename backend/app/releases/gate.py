from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.releases.plan import Evidence

ARTIFACT_PROMOTION_ENVIRONMENTS = frozenset({"prod"})


@dataclass(frozen=True)
class GateContext:
    environment: str
    artifact_digest: str
    evidence: Evidence
    last_stage_artifact: str | None


class GateRule(ABC):
    """One automated quality-gate check. Add rules to GateEvaluator to extend the gate."""

    @abstractmethod
    def findings(self, context: GateContext) -> list[str]:
        ...


class TestsPassedRule(GateRule):
    def findings(self, context):
        return [] if context.evidence.tests_passed else ["Tests did not pass."]


class VulnerabilityRule(GateRule):
    def findings(self, context):
        critical = context.evidence.critical_vulnerabilities
        high = context.evidence.high_vulnerabilities
        return [f"{critical} critical and {high} high vulnerabilities must be fixed."] if critical or high else []


class SignedProvenanceRule(GateRule):
    def findings(self, context):
        return [] if context.evidence.signed else ["The artifact provenance is not signed."]


class SameArtifactAsStageRule(GateRule):
    def findings(self, context):
        if context.environment not in ARTIFACT_PROMOTION_ENVIRONMENTS:
            return []
        if context.last_stage_artifact == context.artifact_digest:
            return []
        return ["PROD must deploy the artifact that ran in QA/STAGE."]


class GateEvaluator:
    def __init__(self, rules: list[GateRule]):
        self._rules = rules

    @classmethod
    def default(cls) -> "GateEvaluator":
        return cls([TestsPassedRule(), VulnerabilityRule(), SignedProvenanceRule(), SameArtifactAsStageRule()])

    def findings(self, context: GateContext) -> list[str]:
        return [finding for rule in self._rules for finding in rule.findings(context)]
