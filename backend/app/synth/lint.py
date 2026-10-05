from abc import ABC, abstractmethod


class LintError(Exception):
    pass


class LintRule(ABC):
    """One check on a generated document. Each provider registers its rules in its TemplateLinter."""

    @abstractmethod
    def findings(self, template: dict) -> list[str]:
        ...


class TemplateLinter:
    def __init__(self, rules: list[LintRule]):
        self._rules = rules

    def lint(self, template: dict) -> list[str]:
        return [finding for rule in self._rules for finding in rule.findings(template)]

    def assert_clean(self, template: dict) -> None:
        findings = self.lint(template)
        if findings:
            raise LintError("; ".join(findings))
