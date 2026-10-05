import pytest

from app.providers.aws.project.toolkit import aws_binders, aws_blocks
from app.synth.request import ProjectRequest
from app.synth.validation import RequestValidationError, RequestValidator
from tests.factories import dr_request_dict, request_dict, with_resources


@pytest.fixture
def validator() -> RequestValidator:
    return RequestValidator.default(aws_blocks(), aws_binders())


def messages(validator: RequestValidator, payload: dict) -> list[str]:
    try:
        validator.validate(ProjectRequest.model_validate(payload))
    except RequestValidationError as error:
        return error.messages
    return []


def test_valid_request_has_no_messages(validator):
    assert messages(validator, request_dict()) == []


def test_duplicate_resource_ids(validator):
    payload = request_dict(resources=[{"id": "a1", "type": "s3.bucket"}, {"id": "a1", "type": "sqs.queue"}],
                           connections=[])
    assert messages(validator, payload) == ["Duplicate resource id 'a1'."]


def test_connection_to_unknown_resource(validator):
    payload = request_dict(connections=[{"kind": "event.notify", "source": "uploads", "target": "missing"}])
    assert messages(validator, payload) == ["Connection refers to unknown resource 'missing'."]


def test_unknown_resource_type(validator):
    payload = request_dict(resources=[{"id": "box", "type": "made.up"}], connections=[])
    assert messages(validator, payload) == ["Unknown resource type 'made.up' for 'box'."]


def test_event_notify_direction_enforced(validator):
    payload = request_dict(connections=[{"kind": "event.notify", "source": "processor", "target": "uploads"}])
    assert messages(validator, payload) == ["event.notify cannot connect compute.function to storage.bucket."]


def test_iam_access_requires_access_level(validator):
    payload = request_dict(connections=[{"kind": "iam.access", "source": "processor", "target": "uploads"}])
    assert messages(validator, payload) == ["iam.access from 'processor' to 'uploads' needs an access level."]


def test_iam_access_target_must_be_access_target(validator):
    payload = with_resources({"id": "other", "type": "lambda.function"}, connections=[
        {"kind": "iam.access", "source": "processor", "target": "other", "access": "read"}])
    assert messages(validator, payload) == ["iam.access cannot connect compute.function to compute.function."]


def test_unknown_connection_kind(validator):
    payload = request_dict(connections=[{"kind": "made.up", "source": "uploads", "target": "processor"}])
    assert messages(validator, payload) == ["Unknown connection kind 'made.up'."]


def test_dr_needs_secondary_region(validator):
    payload = request_dict(resilience={"mode": "dr", "primary_region": "us-east-1", "secondary_region": None})
    assert messages(validator, payload) == ["A dr project needs a secondary region."]


def test_dr_regions_must_differ(validator):
    payload = request_dict(resilience={"mode": "ha", "primary_region": "us-east-1",
                                       "secondary_region": "us-east-1"})
    assert messages(validator, payload) == ["Primary and secondary regions must be different."]


def test_valid_dr_request(validator):
    assert messages(validator, dr_request_dict()) == []


def test_bucket_name_too_long(validator):
    payload = request_dict(project_name="a" * 28, resources=[{"id": "uploadsbucket", "type": "s3.bucket"}],
                           connections=[])
    assert messages(validator, payload) == ["Bucket 'uploadsbucket' makes the S3 bucket name too long."]


def test_recursive_write_is_rejected(validator):
    payload = request_dict(connections=[
        {"kind": "event.notify", "source": "uploads", "target": "processor", "prefix": "incoming/"},
        {"kind": "iam.access", "source": "processor", "target": "uploads", "access": "write", "prefix": ""}])
    assert messages(validator, payload) == [
        "'processor' writes to 'uploads' where it is triggered: this would invoke itself recursively."]


def test_write_to_different_prefix_is_allowed(validator):
    payload = request_dict(connections=[
        {"kind": "event.notify", "source": "uploads", "target": "processor", "prefix": "incoming/"},
        {"kind": "iam.access", "source": "processor", "target": "uploads", "access": "write",
         "prefix": "processed/"}])
    assert messages(validator, payload) == []


def test_read_access_never_recursive(validator):
    payload = request_dict(connections=[
        {"kind": "event.notify", "source": "uploads", "target": "processor"},
        {"kind": "iam.access", "source": "processor", "target": "uploads", "access": "read"}])
    assert messages(validator, payload) == []


def test_error_message_lists_all_problems():
    error = RequestValidationError(["first", "second"])
    assert str(error) == "first; second"
