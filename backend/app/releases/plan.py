from typing import Literal

from pydantic import BaseModel, Field

ChangeAction = Literal["Add", "Modify", "Remove"]


class ChangeSpec(BaseModel):
    """One row of a CloudFormation change set."""

    action: ChangeAction
    logical_id: str
    resource_type: str
    replacement: bool = False


class Evidence(BaseModel):
    """What the pipeline proves about the commit before a release can be approved."""

    tests_passed: bool
    critical_vulnerabilities: int = Field(default=0, ge=0)
    high_vulnerabilities: int = Field(default=0, ge=0)
    signed: bool


class PlanSubmission(BaseModel):
    """Sent by the pipeline's plan job: a change set for one environment plus its evidence."""

    project_name: str
    environment: str
    commit_sha: str
    artifact_digest: str
    changes: list[ChangeSpec]
    evidence: Evidence
    requested_by: str
