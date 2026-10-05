import pytest

from app.errors import ValidationFailedError
from app.projects.service import ProjectService
from app.synth.binders.registry import BinderRegistry
from app.synth.blocks.registry import BlockRegistry
from app.synth.lint import CfnLintRunner, LintRule, TemplateLinter
from app.synth.render import RepositoryBundle
from app.synth.request import ProjectRequest
from app.synth.validation import RequestValidationError, RequestValidator
from tests.factories import request_dict
from tests.synth_helpers import synthesize

BLOCKS = BlockRegistry.default()
TOPIC = {"id": "alerts", "type": "AWS::SNS::Topic", "config": {"properties": {"DisplayName": "Alerts"}}}


def payload_with(*resources: dict, connections: list | None = None) -> dict:
    return request_dict(resources=list(resources), connections=connections or [])


def messages(payload: dict) -> list[str]:
    try:
        RequestValidator.default(BLOCKS, BinderRegistry.default()).validate(ProjectRequest.model_validate(payload))
    except RequestValidationError as error:
        return error.messages
    return []


def test_any_cloudformation_type_is_available():
    assert BLOCKS.has_type("AWS::SNS::Topic")


def test_platform_managed_types_are_not_available():
    assert not BLOCKS.has_type("AWS::IAM::User")


def test_curated_equivalents_are_not_available_raw():
    assert not BLOCKS.has_type("AWS::S3::Bucket")


def test_unknown_aws_type_is_not_available():
    assert not BLOCKS.has_type("AWS::Made::Up")


def test_generic_block_class_is_reused():
    assert BLOCKS.block_class("AWS::SNS::Topic") is BLOCKS.block_class("AWS::SNS::Topic")


def test_generic_block_describes_itself():
    block_class = BLOCKS.block_class("AWS::SNS::Topic")
    assert (block_class.display_name, block_class.category) == ("AWS::SNS::Topic", "Schema-driven (Tier 2)")


def test_generic_resource_passes_properties_through():
    template = synthesize(payload_with(TOPIC))
    assert template["Resources"]["AlertsTopic"] == {"Type": "AWS::SNS::Topic",
                                                    "Properties": {"DisplayName": "Alerts"}}


def test_generic_resource_without_properties():
    template = synthesize(payload_with({"id": "alerts", "type": "AWS::SNS::Topic"}))
    assert template["Resources"]["AlertsTopic"] == {"Type": "AWS::SNS::Topic"}


def test_generic_resource_output():
    assert synthesize(payload_with(TOPIC))["Outputs"]["AlertsTopicRef"] == {"Value": {"Ref": "AlertsTopic"}}


def test_generic_resource_in_contract():
    template = synthesize(payload_with(TOPIC))
    assert '"cloudformationType": "AWS::SNS::Topic"' in template["Resources"]["ContractParameter"]["Properties"][
        "Value"]["Fn::Sub"]


def test_valid_generic_request():
    assert messages(payload_with(TOPIC)) == []


def test_missing_required_property():
    subscription = {"id": "sub", "type": "AWS::SNS::Subscription", "config": {"properties": {"Protocol": "sqs"}}}
    assert messages(payload_with(subscription)) == ["AWS::SNS::Subscription 'sub' needs property 'TopicArn'."]


def test_raw_type_with_curated_block_is_redirected():
    assert messages(payload_with({"id": "raw", "type": "AWS::S3::Bucket"})) == [
        "Use the curated service 's3.bucket' instead of 'AWS::S3::Bucket' for 'raw'."]


def test_platform_managed_type_is_refused():
    assert messages(payload_with({"id": "user1", "type": "AWS::IAM::User"})) == [
        "'AWS::IAM::User' for 'user1' is managed by the platform and cannot be requested."]


def test_unknown_aws_type_is_reported():
    assert messages(payload_with({"id": "x1", "type": "AWS::Made::Up"})) == [
        "Unknown resource type 'AWS::Made::Up' for 'x1'."]


def test_generic_resource_cannot_be_an_access_target():
    payload = payload_with({"id": "processor", "type": "lambda.function"}, TOPIC, connections=[
        {"kind": "iam.access", "source": "processor", "target": "alerts", "access": "write"}])
    assert messages(payload) == ["iam.access cannot connect lambda.function to AWS::SNS::Topic."]


def test_generic_template_passes_cfn_lint():
    subscription = {"id": "sub", "type": "AWS::SNS::Subscription", "config": {"properties": {
        "Protocol": "email", "Endpoint": "ops@example.com", "TopicArn": {"Ref": "AlertsTopic"}}}}
    payload = payload_with(TOPIC, subscription)
    files = RepositoryBundle.default().render(ProjectRequest.model_validate(payload), synthesize(payload))
    assert CfnLintRunner().errors(files["template.yaml"]) == []


def test_curated_types_listed_in_catalog_stay_curated():
    assert BLOCKS.type_names() == ["dynamodb.table", "lambda.function", "s3.bucket", "sqs.queue"]


# ---- creation refuses templates with lint findings ----

class AlwaysFinding(LintRule):
    def findings(self, template: dict) -> list[str]:
        return ["AlertsTopic: not allowed in this test"]


def test_create_refuses_templates_with_lint_findings(seeded):
    service = ProjectService.for_session(seeded)
    service._linter = TemplateLinter([AlwaysFinding()])
    with pytest.raises(ValidationFailedError, match="not allowed in this test"):
        service.create(ProjectRequest.model_validate(payload_with(TOPIC)), "key-lint")


# ---- API ----

def test_cloudformation_catalog_search(client):
    types = [entry["type"] for entry in client.get("/v1/catalog/aws/types", params={"search": "sns"}).json()]
    assert "AWS::SNS::Topic" in types


def test_preview_with_generic_resource(client):
    response = client.post("/v1/projects:preview", json=payload_with(TOPIC))
    assert "AlertsTopic" in response.json()["files"]["template.yaml"]
