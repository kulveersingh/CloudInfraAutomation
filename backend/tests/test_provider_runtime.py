import pathlib
import re

import pytest

from app.adapters.factory import AdapterFactory
from app.adapters.local_aws import LocalAws
from app.adapters.ports import BootstrapRequest, CloudPorts
from app.errors import NotFoundError
from app.providers.aws.provider import AwsProvider
from app.synth.request import ProjectRequest
from tests.factories import request_dict

APP = pathlib.Path(__file__).resolve().parent.parent / "app"
AWS_SPECIFICS = re.compile(r"AWS::|arn:aws|aws:[A-Z]|\$\{AWS::|from app\.providers\.aws|import boto3|cfnlint|AWS_[A-Z]")
NEUTRAL_PACKAGES = ("synth", "provisioning", "teardown", "releases")


# ---- one adapter per cloud ----

def test_factory_builds_a_port_per_registered_cloud(settings):
    assert isinstance(AdapterFactory().clouds(settings).get("aws"), LocalAws)


def test_unknown_cloud_has_no_port(settings):
    with pytest.raises(NotFoundError, match="No adapter for cloud provider 'azure'"):
        AdapterFactory().clouds(settings).get("azure")


def test_cloud_ports_wrap_given_ports(local_aws):
    assert CloudPorts({"aws": local_aws}).get("aws") is local_aws


def test_bootstrap_outputs_are_neutral(local_aws):
    outputs = local_aws.ensure_bootstrap_stack(BootstrapRequest(account_id="222222222222", region="us-east-1",
                                                                project="demo", repository="acme/demo-infra",
                                                                environment="dev"))
    assert (outputs.deployer_identity, outputs.execution_identity) == (
        "arn:aws:iam::222222222222:role/cloudinfra/demo-deploy", "arn:aws:iam::222222222222:role/cloudinfra/demo-cfn-exec")


# ---- teardown toolkit ----

def test_aws_teardown_finds_data_stores():
    stores, problems = AwsProvider().teardown().inventory.for_environment(
        ProjectRequest.model_validate(request_dict()), "prod", "555555555555", ["us-east-1"])
    assert ([store.source_ref for store in stores], problems) == (
        ["arn:aws:s3:::invoice-ingest--uploads-555555555555-us-east-1"], [])


def test_aws_teardown_says_what_aws_backup_cannot_keep():
    assert AwsProvider().teardown().notes == ("CloudWatch Logs: not supported by AWS Backup",)


def test_aws_teardown_vault_name():
    assert AwsProvider().teardown().vault_name("eu-west-1", "999999999999") == "cloudinfra-teardown-eu-west-1"


# ---- release risk ----

@pytest.mark.parametrize("resource_type, stateful, permission", [
    ("AWS::S3::Bucket", True, False), ("AWS::DynamoDB::GlobalTable", True, False),
    ("AWS::IAM::Role", False, True), ("AWS::Lambda::Permission", False, True), ("AWS::S3::BucketPolicy", False, True),
    ("AWS::Lambda::Function", False, False),
])
def test_aws_classifies_plan_rows(resource_type, stateful, permission):
    classifier = AwsProvider().resources()
    assert (classifier.is_stateful(resource_type), classifier.is_permission(resource_type)) == (stateful, permission)


# ---- the core stays cloud-neutral ----

@pytest.mark.parametrize("package", NEUTRAL_PACKAGES)
def test_core_runtime_has_no_aws_specifics(package):
    offenders = [str(path.relative_to(APP)) for path in sorted((APP / package).rglob("*.py"))
                 if AWS_SPECIFICS.search(path.read_text())]
    assert offenders == []
