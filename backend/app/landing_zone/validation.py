from abc import ABC, abstractmethod
from collections import Counter

from app.landing_zone.catalog.mappings import ProviderControls
from app.landing_zone.catalog.packs import PackRegistry
from app.landing_zone.catalog.resolver import PackResolver
from app.landing_zone.design import LandingZoneDesign, OuNode


class DesignRule(ABC):
    """One invariant of a landing zone design. New invariants add a rule."""

    @abstractmethod
    def problems(self, design: LandingZoneDesign) -> list[str]:
        ...


class EnvironmentOusAreSeparate(DesignRule):
    """R1: every environment has its own OU, and no environment OU sits inside another one."""

    def problems(self, design):
        environment_ous = {ou.environment for ou in design.environment_ous()}
        missing = [f"Environment '{environment.id}' must have its own OU."
                   for environment in design.answers.environments() if environment.id not in environment_ous]
        return missing + [problem for ou in design.environment_ous() for problem in self._nested(ou)]

    def _nested(self, ou: OuNode) -> list[str]:
        return [f"Environment OU '{inner.name}' must not be inside another environment OU ('{ou.name}')."
                for inner in _descendants(ou) if inner.kind == "environment"]


class SingleSecurityOu(DesignRule):
    """R3: exactly one Security (Cyber) OU."""

    def problems(self, design):
        count = sum(1 for ou in design.walk() if ou.kind == "security")
        return [] if count == 1 else [f"There must be exactly one Security OU (found {count})."]


class UniqueOuNames(DesignRule):
    def problems(self, design):
        counts = Counter(ou.name for ou in design.walk())
        return [f"OU name '{name}' is used more than once." for name, count in counts.items() if count > 1]


class UniqueAccountNames(DesignRule):
    def problems(self, design):
        counts = Counter(account.name for account in design.walk_accounts())
        return [f"Account name '{name}' is used more than once." for name, count in counts.items() if count > 1]


class AccountsStayInTheirDomain(DesignRule):
    """R1: an environment OU (and the OUs below it) holds only that environment's accounts."""

    def problems(self, design):
        return [f"Account '{account.name}' belongs to isolation domain '{account.domain}' but is in OU '{ou.name}'."
                for ou in design.walk() for account in ou.accounts
                if account.domain and account.domain != ou.isolation_domain]


class DesignValidator:
    def __init__(self, rules: list[DesignRule]):
        self._rules = rules

    @classmethod
    def default(cls) -> "DesignValidator":
        return cls([EnvironmentOusAreSeparate(), SingleSecurityOu(), UniqueOuNames(), UniqueAccountNames(),
                    AccountsStayInTheirDomain()])

    def problems(self, design: LandingZoneDesign) -> list[str]:
        return [problem for rule in self._rules for problem in rule.problems(design)]


def _descendants(ou: OuNode) -> list[OuNode]:
    return [node for child in ou.children for node in (child, *_descendants(child))]



class DesignWarning(ABC):
    """Advice shown with a proposal that doesn't block approval. New advice adds a class."""

    @abstractmethod
    def warnings(self, design: LandingZoneDesign) -> list[str]:
        ...


class ControlPackWarnings(DesignWarning):
    """Packs that reach no OU, and what the cloud's controls still need (e.g. an unresolved prerequisite)."""

    def __init__(self, controls: ProviderControls):
        self._controls = controls

    def warnings(self, design):
        return PackResolver(PackRegistry.default(), self._controls).resolve(design).warnings


class DesignAdvisor:
    def __init__(self, rules: list[DesignWarning]):
        self.rules = rules

    @classmethod
    def for_cloud(cls, controls: ProviderControls, advice: tuple[DesignWarning, ...]) -> "DesignAdvisor":
        """The neutral advice plus the cloud's own."""
        return cls([ControlPackWarnings(controls), *advice])

    def warnings(self, design: LandingZoneDesign) -> list[str]:
        return [warning for rule in self.rules for warning in rule.warnings(design)]
