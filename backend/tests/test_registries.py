import pytest

from app.providers.aws.project.capabilities import AwsBlock
from app.providers.aws.project.dialect import CloudFormationDialect
from app.providers.aws.project.toolkit import aws_binders, aws_blocks
from app.synth.binders.base import Binder
from app.synth.binders.registry import UnknownConnectionKindError
from app.synth.blocks.registry import UnknownBlockTypeError
from app.synth.request import ProjectRequest
from app.synth.synthesizer import TemplateSynthesizer
from tests.factories import request_dict


class TopicBlock(AwsBlock):
    type_name = "sns.topic"
    display_name = "SNS topic"
    category = "Integration"
    multi_region = "regional"

    def emit(self, template) -> None:
        template.add_resource(self.naming.logical_id("Topic"), {"Type": "AWS::SNS::Topic"})


class AuditBinder(Binder):
    kind = "audit.link"

    def accepts(self, source_type, target_type) -> bool:
        return True

    def bind(self, connection, source, target, template) -> None:
        template.add_output("AuditLink", {"Value": f"{source.spec.id}->{target.spec.id}"})


def test_default_block_types():
    assert aws_blocks().type_names() == ["compute.function", "database.table", "messaging.queue", "storage.bucket"]


def test_unknown_block_type_raises():
    with pytest.raises(UnknownBlockTypeError):
        aws_blocks().block_class("made.up")


def test_block_type_lookup():
    assert aws_blocks().has_type("s3.bucket")


def test_new_block_extends_synthesis_without_modification():
    blocks = aws_blocks()
    blocks.register(TopicBlock)
    payload = request_dict(resources=[{"id": "alerts", "type": "sns.topic"}], connections=[])
    template = TemplateSynthesizer(blocks, aws_binders(), CloudFormationDialect()).synthesize(
        ProjectRequest.model_validate(payload))
    assert template["Resources"]["AlertsTopic"] == {"Type": "AWS::SNS::Topic"}


def test_default_binder_kinds():
    assert aws_binders().kinds() == ["access.grant", "event.notify"]


def test_unknown_binder_raises():
    with pytest.raises(UnknownConnectionKindError):
        aws_binders().binder("made.up")


def test_binder_kind_lookup():
    assert aws_binders().has_kind("iam.access")


def test_new_binder_extends_synthesis_without_modification():
    binders = aws_binders()
    binders.register(AuditBinder())
    payload = request_dict(connections=[{"kind": "audit.link", "source": "uploads", "target": "processor"}])
    template = TemplateSynthesizer(aws_blocks(), binders, CloudFormationDialect()).synthesize(
        ProjectRequest.model_validate(payload))
    assert template["Outputs"]["AuditLink"] == {"Value": "uploads->processor"}


def test_binder_default_problem_message():
    problems = AuditBinder().problems(request_dict()["connections"][0], TopicBlock, TopicBlock)
    assert problems == []
