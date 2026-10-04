from app.adapters.ports import BootstrapRequest


def bootstrap_request(**overrides) -> BootstrapRequest:
    values = {"account_id": "222222222222", "region": "us-east-1", "project": "demo",
              "repository": "acme/demo-infra", "environment": "dev"}
    values.update(overrides)
    return BootstrapRequest(**values)


def test_bootstrap_returns_deploy_role(local_aws):
    outputs = local_aws.ensure_bootstrap_stack(bootstrap_request())
    assert outputs.deploy_role_arn == "arn:aws:iam::222222222222:role/cloudinfra/demo-deploy"


def test_bootstrap_returns_execution_role(local_aws):
    outputs = local_aws.ensure_bootstrap_stack(bootstrap_request())
    assert outputs.cfn_execution_role_arn == "arn:aws:iam::222222222222:role/cloudinfra/demo-cfn-exec"


def test_bootstrap_records_trust_subject(local_aws):
    local_aws.ensure_bootstrap_stack(bootstrap_request())
    assert local_aws.stacks()[0]["trust_subject"] == "repo:acme/demo-infra:environment:dev"


def test_bootstrap_is_idempotent(local_aws):
    local_aws.ensure_bootstrap_stack(bootstrap_request())
    local_aws.ensure_bootstrap_stack(bootstrap_request())
    assert len(local_aws.stacks()) == 1


def test_bootstrap_per_region(local_aws):
    local_aws.ensure_bootstrap_stack(bootstrap_request())
    local_aws.ensure_bootstrap_stack(bootstrap_request(region="us-east-2"))
    assert len(local_aws.stacks()) == 2


def test_delete_bootstrap(local_aws):
    local_aws.ensure_bootstrap_stack(bootstrap_request())
    local_aws.delete_bootstrap_stack(bootstrap_request())
    assert local_aws.stacks() == []


def test_delete_missing_bootstrap_is_harmless(local_aws):
    assert local_aws.delete_bootstrap_stack(bootstrap_request()) is None
