import uuid

import pytest
from sqlalchemy import select

from app.db import models
from app.errors import ConflictError, ForbiddenError, NotFoundError, ValidationFailedError
from app.releases.executor import ExecutionResult, LocalReleaseExecutor, ReleaseExecutor
from app.releases.policy import Actor
from app.releases.service import ReleaseService
from tests.factories import request_dict
from tests.release_factories import ARTIFACT, change, plan

REVIEWER = Actor("sam", frozenset({"reviewer"}))
ADMIN = Actor("alex", frozenset({"platform-admin", "reviewer"}))
HIGH_RISK = [change("Modify", "AWS::S3::Bucket", replacement=True, logical_id="UploadsBucket")]


class FailingExecutor(ReleaseExecutor):
    def execute(self, release) -> ExecutionResult:
        return ExecutionResult(False, "ExecuteChangeSet failed: boom")


@pytest.fixture
def project(seeded):
    seeded.add(models.Project(name="invoice-ingest", portfolio_id="pf-payments", product_id="pr-invoicing",
                              resilience_mode="single", status="active", request=request_dict()))
    seeded.commit()
    return seeded


@pytest.fixture
def service(project, tmp_path) -> ReleaseService:
    return ReleaseService.for_session(project, LocalReleaseExecutor(tmp_path))


def deploy_stage(service: ReleaseService, artifact: str = ARTIFACT) -> dict:
    release = service.submit_plan(plan("stage", artifact=artifact))
    return service.approve(uuid.UUID(release["id"]), REVIEWER, "ok")


# ---- submitting plans ----

def test_dev_release_deploys_without_approval(service):
    assert service.submit_plan(plan("dev"))["state"] == "deployed"


def test_stage_release_waits_for_approval(service):
    assert service.submit_plan(plan("stage"))["state"] == "awaiting_approval"


def test_failed_gate_blocks_release(service):
    release = service.submit_plan(plan("stage", tests_passed=False))
    assert (release["state"], release["gate_findings"]) == ("gate_failed", ["Tests did not pass."])


def test_high_risk_release_needs_override(service):
    assert service.submit_plan(plan("stage", changes=HIGH_RISK))["state"] == "override_requested"


def test_changes_are_classified(service):
    release = service.submit_plan(plan("stage", changes=HIGH_RISK))
    assert (release["risk"], release["changes"][0]["risk"]) == ("high", "high")


def test_unknown_project(service):
    with pytest.raises(NotFoundError):
        service.submit_plan(plan("stage", project="nope"))


def test_environment_not_enabled_for_project(service):
    with pytest.raises(ValidationFailedError, match="sandbox is not enabled for invoice-ingest"):
        service.submit_plan(plan("sandbox"))


def test_new_plan_supersedes_pending_release(service):
    first = service.submit_plan(plan("stage"))
    service.submit_plan(plan("stage"))
    assert service.get(uuid.UUID(first["id"]))["state"] == "superseded"


# ---- approving and rejecting ----

def test_approval_deploys(service):
    assert deploy_stage(service)["state"] == "deployed"


def test_approval_is_recorded(service):
    release = deploy_stage(service)
    assert [(item["actor"], item["kind"], item["comment"]) for item in release["decisions"]] == [
        ("sam", "approve", "ok")]


def test_approval_is_audited(service, project):
    deploy_stage(service)
    assert project.scalars(select(models.AuditEntry.action)).all() == ["release.approve"]


def test_requester_cannot_approve(service):
    release = service.submit_plan(plan("stage"))
    with pytest.raises(ForbiddenError):
        service.approve(uuid.UUID(release["id"]), Actor("jordan", frozenset({"reviewer"})), "")


def test_only_pending_releases_can_be_approved(service):
    release = service.submit_plan(plan("dev"))
    with pytest.raises(ConflictError):
        service.approve(uuid.UUID(release["id"]), REVIEWER, "")


def test_rejection(service):
    release = service.submit_plan(plan("stage"))
    assert service.reject(uuid.UUID(release["id"]), REVIEWER, "not now")["state"] == "rejected"


def test_failed_execution_rolls_back(project):
    service = ReleaseService.for_session(project, FailingExecutor())
    assert service.submit_plan(plan("dev"))["state"] == "rolled_back"


def test_failed_execution_keeps_the_reason(project):
    service = ReleaseService.for_session(project, FailingExecutor())
    assert service.submit_plan(plan("dev"))["execution_detail"] == "ExecuteChangeSet failed: boom"


# ---- overrides ----

def test_override_leads_to_normal_approval(service):
    release = service.submit_plan(plan("stage", changes=HIGH_RISK))
    assert service.approve_override(uuid.UUID(release["id"]), ADMIN, "cache only")["state"] == "awaiting_approval"


def test_override_in_lower_environment_deploys(service):
    release = service.submit_plan(plan("dev", changes=HIGH_RISK))
    assert service.approve_override(uuid.UUID(release["id"]), ADMIN, "ok")["state"] == "deployed"


def test_override_needs_platform_admin(service):
    release = service.submit_plan(plan("stage", changes=HIGH_RISK))
    with pytest.raises(ForbiddenError):
        service.approve_override(uuid.UUID(release["id"]), REVIEWER, "")


def test_override_rejection(service):
    release = service.submit_plan(plan("stage", changes=HIGH_RISK))
    assert service.reject(uuid.UUID(release["id"]), ADMIN, "too risky")["state"] == "rejected"


# ---- PROD needs the STAGE artifact ----

def test_prod_before_stage_is_blocked(service):
    assert service.submit_plan(plan("prod"))["state"] == "gate_failed"


def test_prod_after_stage_waits_for_approval(service):
    deploy_stage(service)
    assert service.submit_plan(plan("prod"))["state"] == "awaiting_approval"


def test_prod_with_different_artifact_is_blocked(service):
    deploy_stage(service)
    assert service.submit_plan(plan("prod", artifact="sha256:bbbb"))["state"] == "gate_failed"


# ---- views ----

def test_reviewer_inbox_shows_awaiting_releases(service):
    service.submit_plan(plan("stage"))
    service.submit_plan(plan("dev", changes=HIGH_RISK))
    assert [item["state"] for item in service.inbox(REVIEWER)] == ["awaiting_approval"]


def test_admin_inbox_includes_overrides(service):
    service.submit_plan(plan("stage"))
    service.submit_plan(plan("dev", changes=HIGH_RISK))
    assert sorted(item["state"] for item in service.inbox(ADMIN)) == ["awaiting_approval", "override_requested"]


def test_pipeline_shows_latest_release_per_environment(service):
    service.submit_plan(plan("dev"))
    pipeline = service.pipeline("invoice-ingest")
    assert [(stage["environment"], stage["release"] and stage["release"]["state"]) for stage in pipeline] == [
        ("dev", "deployed"), ("test", None), ("stage", None), ("prod", None)]


def test_pipeline_marks_gated_environments(service):
    assert [stage["requires_approval"] for stage in service.pipeline("invoice-ingest")] == [
        False, False, True, True]


def test_pipeline_of_unknown_project(service):
    with pytest.raises(NotFoundError):
        service.pipeline("nope")


def test_releases_can_be_listed_by_project(service):
    service.submit_plan(plan("dev"))
    assert len(service.releases("invoice-ingest")) == 1


def test_all_releases_listed_without_filter(service):
    service.submit_plan(plan("dev"))
    assert len(service.releases(None)) == 1


def test_unknown_release(service):
    with pytest.raises(NotFoundError):
        service.get(uuid.uuid4())
