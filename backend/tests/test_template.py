import pytest

from app.synth.template import DuplicateLogicalIdError, Template


def test_empty_template_has_format_version():
    assert Template().to_dict()["AWSTemplateFormatVersion"] == "2010-09-09"


def test_added_resource_appears():
    template = Template()
    template.add_resource("Queue", {"Type": "AWS::SQS::Queue"})
    assert template.to_dict()["Resources"] == {"Queue": {"Type": "AWS::SQS::Queue"}}


def test_duplicate_resource_is_rejected():
    template = Template()
    template.add_resource("Queue", {"Type": "AWS::SQS::Queue"})
    with pytest.raises(DuplicateLogicalIdError):
        template.add_resource("Queue", {"Type": "AWS::SQS::Queue"})


def test_resource_can_be_fetched_for_amendment():
    template = Template()
    template.add_resource("Queue", {"Type": "AWS::SQS::Queue"})
    template.resource("Queue")["Properties"] = {"DelaySeconds": 0}
    assert template.to_dict()["Resources"]["Queue"]["Properties"] == {"DelaySeconds": 0}


def test_parameters_conditions_outputs_are_kept():
    template = Template()
    template.add_parameter("ProjectName", {"Type": "String"})
    template.add_condition("IsActive", {"Fn::Equals": ["a", "a"]})
    template.add_output("Name", {"Value": "x"})
    sections = template.to_dict()
    assert (sections["Parameters"], sections["Conditions"], sections["Outputs"]) == (
        {"ProjectName": {"Type": "String"}}, {"IsActive": {"Fn::Equals": ["a", "a"]}}, {"Name": {"Value": "x"}})


def test_has_resource_type():
    template = Template()
    template.add_resource("Fn", {"Type": "AWS::Lambda::Function"})
    assert template.has_resource_type("AWS::Lambda::Function")


def test_empty_sections_are_omitted():
    assert set(Template().to_dict()) == {"AWSTemplateFormatVersion", "Description", "Resources"}


def test_metadata_is_included_when_set():
    template = Template()
    template.set_metadata({"Generator": {"name": "x"}})
    assert template.to_dict()["Metadata"] == {"Generator": {"name": "x"}}
