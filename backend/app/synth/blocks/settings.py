import re
from abc import ABC, abstractmethod
from typing import ClassVar


class Setting(ABC):
    """One `config` key a curated block accepts. The declaration validates, defaults and describes it to the UI."""

    kind: ClassVar[str]

    def __init__(self, name: str, label: str, default):
        self.name = name
        self.label = label
        self.default = default

    @abstractmethod
    def problems(self, value) -> list[str]:
        """Why the value is not allowed, phrased to follow "setting '<name>'"."""

    def describe(self) -> dict:
        return {"kind": self.kind, "name": self.name, "label": self.label, "default": self.default, **self._details()}

    @abstractmethod
    def _details(self) -> dict:
        ...


class ChoiceSetting(Setting):
    kind = "choice"

    def __init__(self, name: str, label: str, default: str, choices: tuple[str, ...]):
        super().__init__(name, label, default)
        self.choices = choices

    def problems(self, value):
        return [] if value in self.choices else [f"must be one of {', '.join(self.choices)}"]

    def _details(self):
        return {"choices": list(self.choices)}


class IntegerSetting(Setting):
    kind = "integer"

    def __init__(self, name: str, label: str, default: int, minimum: int, maximum: int, unit: str):
        super().__init__(name, label, default)
        self.minimum = minimum
        self.maximum = maximum
        self.unit = unit

    def problems(self, value):
        whole = isinstance(value, int) and not isinstance(value, bool)
        if whole and self.minimum <= value <= self.maximum:
            return []
        return [f"must be a whole number from {self.minimum} to {self.maximum} {self.unit}"]

    def _details(self):
        return {"minimum": self.minimum, "maximum": self.maximum, "unit": self.unit}


class TextSetting(Setting):
    """Text matching a pattern; the pattern is also checked in the browser, so it uses syntax both understand."""

    kind = "text"

    def __init__(self, name: str, label: str, default: str | None, pattern: str, rule: str, optional: bool = False):
        super().__init__(name, label, default)
        self.pattern = pattern
        self.rule = rule
        self.optional = optional

    def problems(self, value):
        return [] if isinstance(value, str) and re.fullmatch(self.pattern, value) else [f"must be {self.rule}"]

    def _details(self):
        return {"pattern": self.pattern, "rule": self.rule, "optional": self.optional}
