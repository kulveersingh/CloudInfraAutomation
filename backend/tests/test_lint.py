import pytest

from app.providers.aws.project.lint import CfnLintRunner, aws_linter
from app.synth.lint import LintError, LintRule, TemplateLinter
from tests.factories import request_dict
from tests.synth_helpers import synthesize

BOUNDARY = {"Fn::Sub": "arn:${AWS::Partition}:iam::${AWS::AccountId}:policy/cloudinfra-app-boundary"}


def role(statements: list, boundary=BOUNDARY) -> dict:
    properties = {"AssumeRolePolicyDocument": {}, "Policies": [
        {"PolicyName": "p", "PolicyDocument": {"Version": "2012-10-17", "Statement": statements}}]}
    if boundary:
        properties["PermissionsBoundary"] = boundary
    return {"Type": "AWS::IAM::Role", "Properties": properties}


def template_with(*resources: tuple) -> dict:
    return {"Resources": dict(resources)}


def allow(action, resource="arn:aws:s3:::b/*") -> dict:
    return {"Effect": "Allow", "Action": action, "Resource": resource}


def same_tag_policy(policy_type: str, target_key: str, target_ref: str, sids: list) -> dict:
    statements = [{"Sid": sid, "Effect": "Deny"} for sid in sids]
    return {"Type": policy_type, "Properties": {target_key: target_ref, "PolicyDocument": {"Statement": statements}}}


LINTER = aws_linter()


def test_clean_role_has_no_findings():
    assert LINTER.lint(template_with(("R", role([allow(["s3:GetObject"])])))) == []


def test_action_as_single_string_is_accepted():
    assert LINTER.lint(template_with(("R", role([allow("s3:GetObject")])))) == []


def test_wildcard_action():
    assert LINTER.lint(template_with(("R", role([allow("*")])))) == ["R: wildcard action '*'."]


def test_service_wildcard_action():
    assert LINTER.lint(template_with(("R", role([allow(["s3:*"])])))) == ["R: wildcard action 's3:*'."]


def test_wildcard_resource():
    assert LINTER.lint(template_with(("R", role([allow(["s3:GetObject"], "*")])))) == [
        "R: wildcard resource '*'."]


def test_wildcard_inside_resource_list():
    assert LINTER.lint(template_with(("R", role([allow(["s3:GetObject"], ["arn:aws:s3:::b", "*"])])))) == [
        "R: wildcard resource '*'."]


@pytest.mark.parametrize("action", ["iam:PassRole", "sts:AssumeRole", "iam:CreateRole"])
def test_forbidden_actions(action):
    assert LINTER.lint(template_with(("R", role([allow([action])])))) == [f"R: forbidden action '{action}'."]


def test_deny_statements_are_ignored():
    deny = {"Effect": "Deny", "Action": "*", "Resource": "*"}
    assert LINTER.lint(template_with(("R", role([deny])))) == []


def test_role_without_boundary():
    assert LINTER.lint(template_with(("R", role([allow(["s3:GetObject"])], boundary=None)))) == [
        "R: role has no permissions boundary."]


def test_role_without_policies_is_fine():
    resource = {"Type": "AWS::IAM::Role", "Properties": {"PermissionsBoundary": BOUNDARY}}
    assert LINTER.lint(template_with(("R", resource))) == []


def test_bucket_without_policy():
    assert LINTER.lint(template_with(("B", {"Type": "AWS::S3::Bucket"}))) == ["B: missing same-tag policy."]


def test_bucket_policy_missing_environment_statement():
    policy = same_tag_policy("AWS::S3::BucketPolicy", "Bucket", {"Ref": "B"}, ["DenyOtherProjects"])
    assert LINTER.lint(template_with(("B", {"Type": "AWS::S3::Bucket"}), ("BP", policy))) == [
        "B: missing same-tag policy."]


def test_bucket_with_complete_policy():
    policy = same_tag_policy("AWS::S3::BucketPolicy", "Bucket", {"Ref": "B"},
                             ["DenyOtherProjects", "DenyOtherEnvironments"])
    assert LINTER.lint(template_with(("B", {"Type": "AWS::S3::Bucket"}), ("BP", policy))) == []


def test_queue_without_policy():
    assert LINTER.lint(template_with(("Q", {"Type": "AWS::SQS::Queue"}))) == ["Q: missing same-tag policy."]


def test_queue_with_complete_policy():
    policy = same_tag_policy("AWS::SQS::QueuePolicy", "Queues", [{"Ref": "Q"}],
                             ["DenyOtherProjects", "DenyOtherEnvironments"])
    assert LINTER.lint(template_with(("Q", {"Type": "AWS::SQS::Queue"}), ("QP", policy))) == []


def test_assert_clean_raises_with_findings():
    with pytest.raises(LintError, match="wildcard action"):
        LINTER.assert_clean(template_with(("R", role([allow("*")]))))


def test_assert_clean_passes_quietly():
    assert LINTER.assert_clean(template_with(("R", role([allow(["s3:GetObject"])])))) is None


def test_custom_rule_extends_linter():
    class NoQueues(LintRule):
        def findings(self, template: dict) -> list[str]:
            return ["no queues allowed"] if "Q" in template["Resources"] else []

    linter = TemplateLinter([NoQueues()])
    assert linter.lint(template_with(("Q", {"Type": "AWS::SQS::Queue"}))) == ["no queues allowed"]


def test_synthesized_templates_are_clean():
    assert LINTER.lint(synthesize(request_dict())) == []


def test_cfn_lint_accepts_valid_template():
    assert CfnLintRunner().errors("Resources:\n  Q:\n    Type: AWS::SQS::Queue\n") == []


def test_cfn_lint_reports_unknown_property():
    errors = CfnLintRunner().errors("Resources:\n  Q:\n    Type: AWS::SQS::Queue\n    Properties:\n"
                                    "      NotAProp: 1\n")
    assert any("NotAProp" in error for error in errors)
