import json
import pathlib
import re

import pytest

from app.providers.aws.provider import AwsProvider
from app.synth.request import ProjectRequest
from tests.factories import request_dict

APP = pathlib.Path(__file__).resolve().parent.parent / "app"
AWS_SPECIFICS = re.compile(r"AWS::|arn:aws|aws:[A-Z]|\$\{AWS::|from app\.providers\.aws|import boto3|cfnlint")
NEUTRAL = {"s3.bucket": "storage.bucket", "lambda.function": "compute.function", "dynamodb.table": "database.table",
           "sqs.queue": "messaging.queue"}


def toolkit():
    return AwsProvider().project()


def neutral(payload: dict) -> dict:
    payload = json.loads(json.dumps(payload))
    for resource in payload["resources"]:
        resource["type"] = NEUTRAL.get(resource["type"], resource["type"])
    for connection in payload["connections"]:
        connection["kind"] = {"iam.access": "access.grant"}.get(connection["kind"], connection["kind"])
    return payload


def synthesize(payload: dict) -> dict:
    return toolkit().synthesizer.synthesize(ProjectRequest.model_validate(payload))


# ---- the toolkit a provider gives the core ----

def test_aws_toolkit_has_every_part():
    kit = toolkit()
    assert all(part is not None for part in (kit.blocks, kit.binders, kit.synthesizer, kit.validator, kit.linter,
                                             kit.bundle, kit.types))


def test_toolkit_is_built_once_per_provider():
    provider = AwsProvider()
    assert provider.project() is provider.project()


# ---- neutral kinds, with the AWS ids as aliases ----

def test_catalog_lists_neutral_kinds():
    assert [entry["type"] for entry in toolkit().catalog()] == [
        "compute.function", "database.table", "messaging.queue", "storage.bucket"]


@pytest.mark.parametrize("alias, kind", NEUTRAL.items())
def test_aws_ids_are_aliases_of_the_neutral_kinds(alias, kind):
    blocks = toolkit().blocks
    assert blocks.block_class(alias) is blocks.block_class(kind)


def test_access_grant_is_the_neutral_connection_kind():
    binders = toolkit().binders
    assert (binders.kinds(), binders.binder("iam.access") is binders.binder("access.grant")) == (
        ["access.grant", "event.notify"], True)


def test_neutral_and_alias_requests_generate_the_same_template():
    payload = request_dict(resources=[*request_dict()["resources"], {"id": "orders", "type": "dynamodb.table"},
                                      {"id": "jobs", "type": "sqs.queue"}],
                           connections=[*request_dict()["connections"],
                                        {"kind": "iam.access", "source": "processor", "target": "orders",
                                         "access": "readwrite"}])
    assert synthesize(neutral(payload)) == synthesize(payload)


def test_neutral_requests_validate():
    toolkit().validator.validate(ProjectRequest.model_validate(neutral(request_dict())))


def test_stored_alias_ids_are_never_rewritten():
    files = toolkit().bundle.render(ProjectRequest.model_validate(request_dict()), synthesize(request_dict()))
    assert [resource["type"] for resource in json.loads(files["infra.json"])["resources"]] == [
        "s3.bucket", "lambda.function"]


def test_settings_problems_name_the_type_as_requested():
    payload = request_dict(resources=[{"id": "processor", "type": "compute.function", "config": {"memory": 1}}],
                           connections=[])
    from app.synth.validation import RequestValidationError
    with pytest.raises(RequestValidationError, match="compute.function 'processor' does not accept 'memory'"):
        toolkit().validator.validate(ProjectRequest.model_validate(payload))


def test_event_notify_defaults_to_object_created_events():
    payload = request_dict()
    payload["connections"][0].pop("events", None)
    configurations = synthesize(payload)["Resources"]["UploadsBucket"]["Properties"]["NotificationConfiguration"]
    assert configurations["Fn::If"][1]["LambdaConfigurations"][0]["Event"] == "s3:ObjectCreated:*"


# ---- the raw-type search per provider ----

def test_resource_types_are_searched_per_provider(client):
    types = [entry["type"] for entry in client.get("/v1/catalog/aws/types", params={"search": "sns"}).json()]
    assert "AWS::SNS::Topic" in types


def test_resource_types_of_an_unknown_provider(client):
    assert client.get("/v1/catalog/oracle/types").status_code == 404


def test_catalog_is_per_provider(client):
    assert client.get("/v1/catalog", params={"provider": "aws"}).json()[0]["type"] == "compute.function"


# ---- the core stays cloud-neutral ----

def test_core_synthesis_has_no_aws_specifics():
    offenders = [str(path.relative_to(APP)) for path in sorted((APP / "synth").rglob("*.py"))
                 if AWS_SPECIFICS.search(path.read_text())]
    assert offenders == []
