import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar


@dataclass(frozen=True)
class CostCenter:
    value: str
    source: str

    def as_dict(self) -> dict:
        return {"value": self.value, "source": self.source}


@dataclass(frozen=True)
class CostCenterContext:
    organization_default: str
    portfolio: str | None
    product: str | None
    project_override: str | None


class CostCenterSource(ABC):
    """One level of the cost center hierarchy."""

    source_name: ClassVar[str]

    @abstractmethod
    def value_from(self, context: CostCenterContext) -> str | None:
        ...

    def resolve(self, context: CostCenterContext) -> CostCenter | None:
        value = self.value_from(context)
        return CostCenter(value, self.source_name) if value else None


class ProjectOverrideSource(CostCenterSource):
    source_name = "project"

    def value_from(self, context):
        return context.project_override


class ProductSource(CostCenterSource):
    source_name = "product"

    def value_from(self, context):
        return context.product


class PortfolioSource(CostCenterSource):
    source_name = "portfolio"

    def value_from(self, context):
        return context.portfolio


class OrganizationDefaultSource(CostCenterSource):
    source_name = "organization"

    def value_from(self, context):
        return context.organization_default


class CostCenterResolver:
    """Chain of responsibility: the first level that has a value wins."""

    def __init__(self, sources: list[CostCenterSource]):
        self._sources = sources

    @classmethod
    def default(cls) -> "CostCenterResolver":
        return cls([ProjectOverrideSource(), ProductSource(), PortfolioSource(), OrganizationDefaultSource()])

    def resolve(self, context: CostCenterContext) -> CostCenter:
        return next(cost_center for cost_center in (source.resolve(context) for source in self._sources)
                    if cost_center is not None)


class CostCenterFormat:
    def __init__(self, pattern: str):
        self._pattern = re.compile(pattern)

    @property
    def pattern(self) -> str:
        return self._pattern.pattern

    def is_valid(self, value: str) -> bool:
        return bool(self._pattern.fullmatch(value))
