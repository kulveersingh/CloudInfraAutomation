from abc import ABC, abstractmethod

ROLE_TYPE = "AWS::IAM::Role"
FORBIDDEN_ACTIONS = frozenset({"iam:PassRole", "sts:AssumeRole", "iam:CreateRole", "iam:PutRolePolicy",
                               "iam:AttachRolePolicy"})
SAME_TAG_STATEMENTS = frozenset({"DenyOtherProjects", "DenyOtherEnvironments"})
PROTECTED_RESOURCES = {
    "AWS::S3::Bucket": ("AWS::S3::BucketPolicy", "Bucket"),
    "AWS::SQS::Queue": ("AWS::SQS::QueuePolicy", "Queues"),
}


class LintError(Exception):
    pass


def as_list(value) -> list:
    return value if isinstance(value, list) else [value]


class LintRule(ABC):
    """One check on a generated template. Add rules to TemplateLinter to extend linting."""

    @abstractmethod
    def findings(self, template: dict) -> list[str]:
        ...

    def resources_of_type(self, template: dict, type_name: str) -> list[tuple[str, dict]]:
        return [(logical_id, body) for logical_id, body in template["Resources"].items() if body["Type"] == type_name]


class RolePolicyRule(LintRule, ABC):
    """Base for rules that inspect each Allow statement of each IAM role."""

    def findings(self, template):
        return [finding for logical_id, role in self.resources_of_type(template, ROLE_TYPE)
                for statement in self._allow_statements(role) for finding in self.check(logical_id, statement)]

    @abstractmethod
    def check(self, logical_id: str, statement: dict) -> list[str]:
        ...

    def _allow_statements(self, role: dict) -> list[dict]:
        policies = role.get("Properties", {}).get("Policies", [])
        return [statement for policy in policies for statement in policy["PolicyDocument"]["Statement"]
                if statement["Effect"] == "Allow"]


class WildcardActionRule(RolePolicyRule):
    def check(self, logical_id, statement):
        return [f"{logical_id}: wildcard action '{action}'." for action in as_list(statement["Action"])
                if action == "*" or action.endswith(":*")]


class WildcardResourceRule(RolePolicyRule):
    def check(self, logical_id, statement):
        return [f"{logical_id}: wildcard resource '*'." for resource in as_list(statement["Resource"])
                if resource == "*"]


class ForbiddenActionRule(RolePolicyRule):
    def check(self, logical_id, statement):
        return [f"{logical_id}: forbidden action '{action}'." for action in as_list(statement["Action"])
                if action in FORBIDDEN_ACTIONS]


class PermissionsBoundaryRule(LintRule):
    def findings(self, template):
        return [f"{logical_id}: role has no permissions boundary."
                for logical_id, role in self.resources_of_type(template, ROLE_TYPE)
                if "PermissionsBoundary" not in role.get("Properties", {})]


class SameTagPolicyRule(LintRule):
    def findings(self, template):
        return [f"{logical_id}: missing same-tag policy."
                for type_name in PROTECTED_RESOURCES
                for logical_id, _ in self.resources_of_type(template, type_name)
                if not self._protected(template, logical_id, *PROTECTED_RESOURCES[type_name])]

    def _protected(self, template: dict, logical_id: str, policy_type: str, target_key: str) -> bool:
        return any({"Ref": logical_id} in as_list(policy["Properties"][target_key])
                   and SAME_TAG_STATEMENTS <= self._sids(policy)
                   for _, policy in self.resources_of_type(template, policy_type))

    def _sids(self, policy: dict) -> set[str]:
        return {statement.get("Sid") for statement in policy["Properties"]["PolicyDocument"]["Statement"]}


class TemplateLinter:
    def __init__(self, rules: list[LintRule]):
        self._rules = rules

    @classmethod
    def default(cls) -> "TemplateLinter":
        return cls([WildcardActionRule(), WildcardResourceRule(), ForbiddenActionRule(), PermissionsBoundaryRule(),
                    SameTagPolicyRule()])

    def lint(self, template: dict) -> list[str]:
        return [finding for rule in self._rules for finding in rule.findings(template)]

    def assert_clean(self, template: dict) -> None:
        findings = self.lint(template)
        if findings:
            raise LintError("; ".join(findings))


class CfnLintRunner:
    """Runs the open-source cfn-lint and returns only error-level findings."""

    REGIONS = ("us-east-1",)

    def errors(self, template_yaml: str) -> list[str]:
        from cfnlint.api import ManualArgs, lint

        matches = lint(template_yaml, config=ManualArgs(regions=list(self.REGIONS)))
        return [str(match) for match in matches if match.rule.severity == "error"]
