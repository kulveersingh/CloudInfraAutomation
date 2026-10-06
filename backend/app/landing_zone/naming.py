from abc import ABC, abstractmethod
from dataclasses import replace

from app.landing_zone.design import AccountPlan


class UnitNamer(ABC):
    """Names the isolation units (accounts, projects) a landing zone vends, the cloud's way (§22.10.3)."""

    @abstractmethod
    def unit(self, suffix: str) -> AccountPlan:
        ...

    def fixed(self, suffix: str) -> AccountPlan:
        """A unit that one questionnaire answer decides; the tree editor leaves it alone."""
        return replace(self.unit(suffix), fixed=True)

    def added(self, suffix: str) -> AccountPlan:
        """A unit the tree editor added; it can be removed again."""
        return replace(self.unit(suffix), added=True)
