import pytest

from app.providers.aws.project.toolkit import aws_binders, aws_blocks, aws_synthesizer
from app.synth.blocks.settings import ChoiceSetting, IntegerSetting, TextSetting
from app.synth.catalog import ServiceCatalog
from app.synth.request import ProjectRequest
from app.synth.validation import RequestValidationError, RequestValidator
from tests.factories import request_dict

KEY_PATTERN = r"^[A-Za-z0-9_.-]{1,255}$"


def resource(type_name: str, config: dict, resource_id: str = "thing") -> dict:
    return {"id": resource_id, "type": type_name, "config": config}


def messages(*resources: dict) -> list[str]:
    payload = request_dict(resources=list(resources), connections=[])
    try:
        RequestValidator.default(aws_blocks(), aws_binders()).validate(
            ProjectRequest.model_validate(payload))
    except RequestValidationError as error:
        return error.messages
    return []


def function_properties(config: dict) -> dict:
    payload = request_dict(resources=[resource("lambda.function", config, "processor")], connections=[])
    template = aws_synthesizer().synthesize(
        ProjectRequest.model_validate(payload))
    return template["Resources"]["ProcessorFunction"]["Properties"]


def table_keys(config: dict) -> list:
    payload = request_dict(resources=[resource("dynamodb.table", config, "orders")], connections=[])
    template = aws_synthesizer().synthesize(
        ProjectRequest.model_validate(payload))
    return template["Resources"]["OrdersTable"]["Properties"]["KeySchema"]


# ---- setting kinds ----

def test_choice_setting_accepts_a_listed_value():
    assert ChoiceSetting("runtime", "Runtime", "a", ("a", "b")).problems("b") == []


@pytest.mark.parametrize("value", ["c", 1, None])
def test_choice_setting_rejects_other_values(value):
    assert ChoiceSetting("runtime", "Runtime", "a", ("a", "b")).problems(value) == ["must be one of a, b"]


def test_choice_setting_description():
    assert ChoiceSetting("runtime", "Runtime", "a", ("a", "b")).describe() == {
        "kind": "choice", "name": "runtime", "label": "Runtime", "default": "a", "choices": ["a", "b"]}


@pytest.mark.parametrize("value", [1, 5, 10])
def test_integer_setting_accepts_whole_numbers_in_range(value):
    assert IntegerSetting("memory_mb", "Memory", 5, 1, 10, "MB").problems(value) == []


@pytest.mark.parametrize("value", [0, 11, 2.5, "5", True])
def test_integer_setting_rejects_values_out_of_range_or_not_whole(value):
    assert IntegerSetting("memory_mb", "Memory", 5, 1, 10, "MB").problems(value) == [
        "must be a whole number from 1 to 10 MB"]


def test_integer_setting_description():
    assert IntegerSetting("memory_mb", "Memory", 5, 1, 10, "MB").describe() == {
        "kind": "integer", "name": "memory_mb", "label": "Memory", "default": 5, "minimum": 1, "maximum": 10,
        "unit": "MB"}


@pytest.mark.parametrize("value", ["pk", "order.id", "a" * 255])
def test_text_setting_accepts_matching_text(value):
    assert TextSetting("partition_key", "Partition key", "pk", KEY_PATTERN, "letters").problems(value) == []


@pytest.mark.parametrize("value", ["", "has space", "a" * 256, 7])
def test_text_setting_rejects_other_text(value):
    assert TextSetting("partition_key", "Partition key", "pk", KEY_PATTERN, "letters").problems(value) == [
        "must be letters"]


def test_text_setting_description():
    assert TextSetting("sort_key", "Sort key", None, KEY_PATTERN, "letters", optional=True).describe() == {
        "kind": "text", "name": "sort_key", "label": "Sort key", "default": None, "pattern": KEY_PATTERN,
        "rule": "letters", "optional": True}


# ---- validation of curated services ----

def test_valid_lambda_settings_have_no_problems():
    config = {"runtime": "java21", "handler": "com.acme.Handler::handle", "memory_mb": 1024, "timeout_sec": 900}
    assert messages(resource("lambda.function", config)) == []


def test_unknown_lambda_setting_names_the_allowed_ones():
    assert messages(resource("lambda.function", {"memory": 1024}, "processor")) == [
        "lambda.function 'processor' does not accept 'memory'; allowed: runtime, handler, memory_mb, timeout_sec."]


def test_curated_service_does_not_take_cloudformation_properties():
    assert messages(resource("lambda.function", {"properties": {"MemorySize": 1024}}, "processor")) == [
        "lambda.function 'processor' does not accept 'properties'; allowed: runtime, handler, memory_mb, timeout_sec."]


@pytest.mark.parametrize("config, problem", [
    ({"memory_mb": 64}, "setting 'memory_mb' must be a whole number from 128 to 10240 MB"),
    ({"timeout_sec": 901}, "setting 'timeout_sec' must be a whole number from 1 to 900 seconds"),
    ({"runtime": "python2.7"}, ("setting 'runtime' must be one of python3.13, python3.12, nodejs22.x, nodejs20.x, "
                                "java21, provided.al2023")),
    ({"handler": "bad handler"}, "setting 'handler' must be 1 to 128 characters of letters, digits and _ . : / $ -"),
])
def test_invalid_lambda_settings(config, problem):
    assert messages(resource("lambda.function", config, "processor")) == [f"lambda.function 'processor' {problem}."]


def test_invalid_table_key():
    assert messages(resource("dynamodb.table", {"sort_key": "created at"}, "orders")) == [
        "dynamodb.table 'orders' setting 'sort_key' must be 1 to 255 characters of letters, digits and _ . -."]


@pytest.mark.parametrize("type_name", ["s3.bucket", "sqs.queue"])
def test_services_without_settings_reject_any_config(type_name):
    assert messages(resource(type_name, {"versioning": False}, "things")) == [
        f"{type_name} 'things' does not accept 'versioning'; it has no settings."]


def test_every_problem_is_reported():
    assert len(messages(resource("lambda.function", {"memory": 1, "timeout_sec": 0}))) == 2


# ---- schema-driven resources ----

def test_schema_driven_resource_accepts_only_properties():
    assert messages(resource("AWS::SNS::Topic", {"properties": {}, "DisplayName": "x"}, "alerts")) == [
        "AWS::SNS::Topic 'alerts' accepts only 'properties' in config, not 'DisplayName'."]


def test_schema_driven_properties_must_be_an_object():
    assert messages(resource("AWS::SNS::Topic", {"properties": ["DisplayName"]}, "alerts")) == [
        "AWS::SNS::Topic 'alerts' properties must be a JSON object."]


# ---- the settings reach the template ----

def test_lambda_defaults_come_from_the_declared_settings():
    properties = function_properties({})
    assert (properties["Runtime"], properties["Handler"], properties["MemorySize"], properties["Timeout"]) == (
        "python3.13", "lambda_function.lambda_handler", 256, 30)


def test_lambda_settings_reach_the_function():
    properties = function_properties({"runtime": "provided.al2023", "handler": "bootstrap", "memory_mb": 2048,
                                      "timeout_sec": 120})
    assert (properties["Runtime"], properties["Handler"], properties["MemorySize"], properties["Timeout"]) == (
        "provided.al2023", "bootstrap", 2048, 120)


def test_table_keys_default_to_a_partition_key_only():
    assert table_keys({}) == [{"AttributeName": "pk", "KeyType": "HASH"}]


def test_table_sort_key_is_added_when_chosen():
    assert table_keys({"partition_key": "tenant", "sort_key": "created"}) == [
        {"AttributeName": "tenant", "KeyType": "HASH"}, {"AttributeName": "created", "KeyType": "RANGE"}]


# ---- catalog ----

def entries() -> dict:
    return {entry["type"]: entry for entry in ServiceCatalog(aws_blocks()).entries()}


def test_catalog_describes_lambda_settings():
    assert [(setting["name"], setting["kind"]) for setting in entries()["compute.function"]["settings"]] == [
        ("runtime", "choice"), ("handler", "text"), ("memory_mb", "integer"), ("timeout_sec", "integer")]


def test_catalog_describes_table_settings():
    settings = entries()["database.table"]["settings"]
    assert [(setting["name"], setting["default"], setting["optional"]) for setting in settings] == [
        ("partition_key", "pk", False), ("sort_key", None, True)]


def test_services_without_settings_list_none():
    assert (entries()["storage.bucket"]["settings"], entries()["messaging.queue"]["settings"]) == ([], [])


def test_catalog_api_includes_settings(client):
    lambda_entry = next(entry for entry in client.get("/v1/catalog").json() if entry["type"] == "compute.function")
    assert lambda_entry["settings"][2] == {"kind": "integer", "name": "memory_mb", "label": "Memory", "default": 256,
                                           "minimum": 128, "maximum": 10240, "unit": "MB"}


def test_preview_rejects_unknown_settings(client):
    payload = request_dict(resources=[resource("lambda.function", {"memory": 1024}, "processor")], connections=[])
    response = client.post("/v1/projects:preview", json=payload)
    assert (response.status_code, "does not accept 'memory'" in response.json()["detail"]) == (422, True)
