from app.releases.gate import GateContext, GateEvaluator, GateRule
from tests.release_factories import ARTIFACT, evidence

GATE = GateEvaluator.default()


def context(environment: str = "stage", stage_artifact: str | None = None, **evidence_overrides) -> GateContext:
    return GateContext(environment=environment, artifact_digest=ARTIFACT, evidence=evidence(**evidence_overrides),
                       last_stage_artifact=stage_artifact)


def test_complete_evidence_passes():
    assert GATE.findings(context()) == []


def test_failed_tests_block():
    assert GATE.findings(context(tests_passed=False)) == ["Tests did not pass."]


def test_critical_vulnerabilities_block():
    assert GATE.findings(context(critical_vulnerabilities=2)) == [
        "2 critical and 0 high vulnerabilities must be fixed."]


def test_high_vulnerabilities_block():
    assert GATE.findings(context(high_vulnerabilities=1)) == ["0 critical and 1 high vulnerabilities must be fixed."]


def test_unsigned_artifact_blocks():
    assert GATE.findings(context(signed=False)) == ["The artifact provenance is not signed."]


def test_prod_needs_the_stage_artifact():
    assert GATE.findings(context("prod", stage_artifact="sha256:other")) == [
        "PROD must deploy the artifact that ran in QA/STAGE."]


def test_prod_without_stage_release_is_blocked():
    assert GATE.findings(context("prod")) == ["PROD must deploy the artifact that ran in QA/STAGE."]


def test_prod_with_stage_artifact_passes():
    assert GATE.findings(context("prod", stage_artifact=ARTIFACT)) == []


def test_lower_environments_skip_artifact_rule():
    assert GATE.findings(context("dev")) == []


def test_custom_rule_extends_gate():
    class ChangeFreeze(GateRule):
        def findings(self, gate_context):
            return ["Change freeze is active."]

    assert GateEvaluator([ChangeFreeze()]).findings(context()) == ["Change freeze is active."]
