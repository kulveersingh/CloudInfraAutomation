from app.adapters.ports import BootstrapRequest


def bootstrap_request(**overrides) -> BootstrapRequest:
    values = {"account_id": "222222222222", "region": "us-east-1", "project": "demo",
              "repository": "acme/demo-infra", "environment": "dev"}
    values.update(overrides)
    return BootstrapRequest(**values)


def test_bootstrap_returns_deploy_role(local_aws):
    outputs = local_aws.ensure_bootstrap_stack(bootstrap_request())
    assert outputs.deployer_identity == "arn:aws:iam::222222222222:role/cloudinfra/demo-deploy"


def test_bootstrap_returns_execution_role(local_aws):
    outputs = local_aws.ensure_bootstrap_stack(bootstrap_request())
    assert outputs.execution_identity == "arn:aws:iam::222222222222:role/cloudinfra/demo-cfn-exec"


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


def test_stack_operations_are_recorded(local_aws):
    local_aws.allow_stack_deletion("222222222222", "us-east-1", "demo")
    local_aws.delete_stack("222222222222", "us-east-1", "demo")
    local_aws.delete_data_store("222222222222", "us-east-1", "AWS::S3::Bucket", "demo--uploads")
    local_aws.import_stack("222222222222", "us-east-1", "demo", ["UploadsBucket"])
    assert [operation["operation"] for operation in local_aws.operations()] == [
        "allow_stack_deletion", "delete_stack", "delete_data_store", "import_stack"]


def test_operations_name_their_target(local_aws):
    local_aws.delete_data_store("222222222222", "us-east-1", "AWS::DynamoDB::Table", "demo--orders")
    [operation] = local_aws.operations()
    assert {key: value for key, value in operation.items() if key != "at"} == {
        "operation": "delete_data_store", "account": "222222222222", "region": "us-east-1",
        "target": "AWS::DynamoDB::Table demo--orders"}


def test_no_operations_yet(local_aws):
    assert local_aws.operations() == []
