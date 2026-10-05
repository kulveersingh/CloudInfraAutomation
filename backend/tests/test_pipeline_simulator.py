import re

from app.providers.aws.provider import AwsProvider
from app.releases.simulator import LocalPipelineSimulator
from app.synth.request import ProjectRequest
from tests.factories import request_dict

SIMULATOR = LocalPipelineSimulator(AwsProvider().project().synthesizer, AwsProvider().resources())
REQUEST = ProjectRequest.model_validate(request_dict())


def simulate(high_risk: bool = False, environment: str = "stage"):
    return SIMULATOR.plan(REQUEST, environment, requested_by="jordan", high_risk=high_risk)


def test_plan_adds_every_generated_resource():
    logical_ids = {item.logical_id for item in simulate().changes}
    assert {"UploadsBucket", "ProcessorFunction", "ProcessorRole"} <= logical_ids


def test_plan_changes_are_additions():
    assert {item.action for item in simulate().changes} == {"Add"}


def test_plan_evidence_passes_the_gate():
    plan = simulate()
    assert (plan.evidence.tests_passed, plan.evidence.signed) == (True, True)


def test_high_risk_plan_replaces_a_stateful_resource():
    replacements = [item for item in simulate(high_risk=True).changes if item.replacement]
    assert [(item.logical_id, item.resource_type) for item in replacements] == [("UploadsBucket", "AWS::S3::Bucket")]


def test_high_risk_plan_without_stateful_resource_adds_none():
    request = ProjectRequest.model_validate(request_dict(
        resources=[{"id": "processor", "type": "lambda.function"}], connections=[]))
    plan = SIMULATOR.plan(request, "stage", requested_by="jordan", high_risk=True)
    assert not any(item.replacement for item in plan.changes)


def test_artifact_is_stable_across_environments():
    assert simulate(environment="stage").artifact_digest == simulate(environment="prod").artifact_digest


def test_plan_records_requester_and_environment():
    plan = simulate()
    assert (plan.requested_by, plan.environment, plan.project_name) == ("jordan", "stage", "invoice-ingest")


def test_commit_looks_like_a_sha():
    assert re.fullmatch(r"[0-9a-f]{12}", simulate().commit_sha)
