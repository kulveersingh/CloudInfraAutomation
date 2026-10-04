"""Builders for release tests."""

from app.releases.plan import ChangeSpec, Evidence, PlanSubmission

ARTIFACT = "sha256:aaaa"


def change(action: str = "Modify", resource_type: str = "AWS::Lambda::Function", replacement: bool = False,
           logical_id: str = "ProcessorFunction") -> ChangeSpec:
    return ChangeSpec(action=action, logical_id=logical_id, resource_type=resource_type, replacement=replacement)


def evidence(**overrides) -> Evidence:
    values = {"tests_passed": True, "critical_vulnerabilities": 0, "high_vulnerabilities": 0, "signed": True}
    values.update(overrides)
    return Evidence(**values)


def plan(environment: str = "stage", project: str = "invoice-ingest", changes: list | None = None,
         requested_by: str = "jordan", artifact: str = ARTIFACT, **evidence_overrides) -> PlanSubmission:
    return PlanSubmission(project_name=project, environment=environment, commit_sha="4f78c64a1b2c",
                          artifact_digest=artifact, changes=changes if changes is not None else [change()],
                          evidence=evidence(**evidence_overrides), requested_by=requested_by)
