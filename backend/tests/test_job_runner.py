import pytest

from app.db import models
from app.provisioning.queue import JobQueue, JobState
from app.provisioning.runner import JobRunner
from tests.factories import dr_request_dict, request_dict

OWNER = "acme-platform"


@pytest.fixture
def queue(seeded) -> JobQueue:
    return JobQueue(seeded)


def start(seeded, queue, payload: dict) -> models.Job:
    seeded.add(models.Project(name=payload["project_name"], portfolio_id=payload["ownership"]["portfolio_id"],
                              product_id=payload["ownership"]["product_id"], resilience_mode=
                              payload["resilience"]["mode"], status="provisioning", request=payload))
    job = queue.enqueue(project_name=payload["project_name"], request_id="req-1", payload=payload)
    return queue.claim_next() or job


def run(seeded, queue, local_github, local_aws, payload: dict) -> models.Job:
    job = start(seeded, queue, payload)
    JobRunner.for_session(seeded, local_github, local_aws, OWNER).run(job)
    return job


def step_names(queue, job) -> list:
    return [step.name for step in queue.steps(job)]


def test_successful_job(seeded, queue, local_github, local_aws):
    assert run(seeded, queue, local_github, local_aws, request_dict()).state == JobState.SUCCEEDED


def test_steps_for_single_region(seeded, queue, local_github, local_aws):
    job = run(seeded, queue, local_github, local_aws, request_dict())
    assert step_names(queue, job) == [
        "create_repository", "bootstrap:dev:us-east-1", "bootstrap:test:us-east-1", "bootstrap:stage:us-east-1",
        "bootstrap:prod:us-east-1", "configure_environments", "commit_files"]


def test_dr_bootstraps_secondary_for_stage_and_prod(seeded, queue, local_github, local_aws):
    job = run(seeded, queue, local_github, local_aws, dr_request_dict())
    assert [name for name in step_names(queue, job) if name.endswith("us-east-2")] == [
        "bootstrap:stage:us-east-2", "bootstrap:prod:us-east-2"]


def test_repository_receives_generated_files(seeded, queue, local_github, local_aws):
    run(seeded, queue, local_github, local_aws, request_dict())
    assert local_github.repository_exists(OWNER, "invoice-ingest-infra")


def test_prod_environment_variables(seeded, queue, local_github, local_aws):
    run(seeded, queue, local_github, local_aws, request_dict())
    variables = local_github.environment(OWNER, "invoice-ingest-infra", "prod")
    assert (variables["AWS_ACCOUNT_ID"], variables["AWS_PRIMARY_REGION"], variables["AWS_ROLE_ARN"]) == (
        "555555555555", "us-east-1", "arn:aws:iam::555555555555:role/cloudinfra/invoice-ingest-deploy")


def test_dr_secondary_variables(seeded, queue, local_github, local_aws):
    run(seeded, queue, local_github, local_aws, dr_request_dict())
    variables = local_github.environment(OWNER, "invoice-ingest-infra", "prod")
    assert (variables["AWS_SECONDARY_REGION"], variables["ACTIVATION_STATE_SECONDARY"]) == ("us-east-2", "standby")


def test_environment_variables_carry_the_network(seeded, queue, local_github, local_aws):
    run(seeded, queue, local_github, local_aws, request_dict())
    variables = local_github.environment(OWNER, "invoice-ingest-infra", "prod")
    assert (variables["VPC_ID"].startswith("vpc-"), len(variables["PRIVATE_SUBNET_IDS"].split(",")),
            variables["ORG_PRIVATE_CIDR"].startswith("10.")) == (True, 3, True)


def test_dr_secondary_region_carries_its_own_network(seeded, queue, local_github, local_aws):
    run(seeded, queue, local_github, local_aws, dr_request_dict())
    variables = local_github.environment(OWNER, "invoice-ingest-infra", "prod")
    assert variables["VPC_ID_SECONDARY"] != variables["VPC_ID"]


def test_detached_project_has_no_network_variables(seeded, queue, local_github, local_aws):
    run(seeded, queue, local_github, local_aws, request_dict(network={"attach_compute": False}))
    assert "VPC_ID" not in local_github.environment(OWNER, "invoice-ingest-infra", "prod")


def test_repository_variables_carry_tags(seeded, queue, local_github, local_aws):
    run(seeded, queue, local_github, local_aws, request_dict())
    variables = local_github.repository_variables(OWNER, "invoice-ingest-infra")
    assert (variables["PROJECT_NAME"], variables["ORG_PRODUCT"], variables["ORG_COST_CENTER"]) == (
        "invoice-ingest", "pr-invoicing", "CC-4410")


def test_project_becomes_active(seeded, queue, local_github, local_aws):
    run(seeded, queue, local_github, local_aws, request_dict())
    assert seeded.get(models.Project, "invoice-ingest").status == "active"


def test_failure_rolls_back_bootstrap_and_repository(seeded, queue, local_github, local_aws, monkeypatch):
    monkeypatch.setattr(local_github, "set_environment", _raise("boom"))
    job = run(seeded, queue, local_github, local_aws, request_dict())
    assert (job.state, local_aws.stacks(), local_github.repository_exists(OWNER, "invoice-ingest-infra")) == (
        JobState.FAILED_ROLLED_BACK, [], False)


def test_failure_marks_project_failed(seeded, queue, local_github, local_aws, monkeypatch):
    monkeypatch.setattr(local_github, "set_environment", _raise("boom"))
    run(seeded, queue, local_github, local_aws, request_dict())
    assert seeded.get(models.Project, "invoice-ingest").status == "failed"


def test_failed_compensation_needs_attention(seeded, queue, local_github, local_aws, monkeypatch):
    monkeypatch.setattr(local_github, "set_environment", _raise("boom"))
    monkeypatch.setattr(local_aws, "delete_bootstrap_stack", _raise("cannot delete"))
    assert run(seeded, queue, local_github, local_aws, request_dict()).state == JobState.FAILED_NEEDS_ATTENTION


def test_repository_of_another_request_is_untouched(seeded, queue, local_github, local_aws):
    local_github.create_repository(OWNER, "invoice-ingest-infra", marker="someone-else")
    job = run(seeded, queue, local_github, local_aws, request_dict())
    assert (job.state, local_github.repository_exists(OWNER, "invoice-ingest-infra")) == (
        JobState.FAILED_ROLLED_BACK, True)


def test_resumed_repository_is_kept_on_failure(seeded, queue, local_github, local_aws, monkeypatch):
    local_github.create_repository(OWNER, "invoice-ingest-infra", marker="req-1")
    monkeypatch.setattr(local_github, "commit_files", _raise("boom"))
    run(seeded, queue, local_github, local_aws, request_dict())
    assert local_github.repository_exists(OWNER, "invoice-ingest-infra")


def _raise(message: str):
    def failing(*args, **kwargs):
        raise RuntimeError(message)

    return failing
