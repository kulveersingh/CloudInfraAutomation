import pytest

from app.providers.aws.project.blocks.cloudformation import (
    CloudFormationSchemaCatalog,
    UnknownResourceTypeError,
)

CATALOG = CloudFormationSchemaCatalog.bundled()


def test_catalog_covers_all_cloudformation_resource_types():
    assert len(CATALOG.type_names()) > 1500


def test_known_type():
    assert CATALOG.has("AWS::SNS::Topic")


def test_unknown_type():
    assert not CATALOG.has("AWS::Made::Up")


def test_required_properties_from_schema():
    assert set(CATALOG.required_properties("AWS::SNS::Subscription")) == {"TopicArn", "Protocol"}


def test_type_without_required_properties():
    assert CATALOG.required_properties("AWS::SNS::Topic") == []


def test_required_properties_of_unknown_type():
    with pytest.raises(UnknownResourceTypeError):
        CATALOG.required_properties("AWS::Made::Up")


def test_service_name():
    assert CATALOG.service("AWS::SNS::Topic") == "SNS"


def test_search_finds_matching_types():
    assert "AWS::SNS::Topic" in [entry["type"] for entry in CATALOG.search("sns")]


def test_search_entry_shape():
    entry = next(item for item in CATALOG.search("sns::subscription"))
    assert entry == {"type": "AWS::SNS::Subscription", "service": "SNS", "required": ["Protocol", "TopicArn"]}


def test_search_is_limited():
    assert len(CATALOG.search("aws", limit=10)) == 10
