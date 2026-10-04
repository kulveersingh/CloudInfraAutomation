from collections.abc import Iterator
from dataclasses import dataclass, field

from app.landing_zone.answers import LandingZoneAnswers


@dataclass(frozen=True)
class OrgCatalog:
    """Portfolio and product ids from the registry, used to name accounts."""

    portfolios: list[str]
    products: list[str]


@dataclass(frozen=True)
class AccountPlan:
    name: str
    email: str


@dataclass
class OuNode:
    key: str
    name: str
    kind: str
    environment: str | None = None
    tier: str | None = None
    created_by_control_tower: bool = False
    children: list["OuNode"] = field(default_factory=list)
    accounts: list[AccountPlan] = field(default_factory=list)

    @property
    def label(self) -> str:
        return f"{self.name} OU"


@dataclass
class LandingZoneDesign:
    """The proposed organization: OU tree with accounts, produced by the designer from the answers."""

    answers: LandingZoneAnswers
    root_ous: list[OuNode] = field(default_factory=list)

    def walk(self) -> Iterator[OuNode]:
        yield from _walk(self.root_ous)

    def ou_named(self, name: str) -> OuNode:
        for ou in self.walk():
            if ou.name == name:
                return ou
        raise KeyError(name)

    def environment_ous(self) -> list[OuNode]:
        return [ou for ou in self.walk() if ou.kind == "environment"]

    def accounts(self) -> list[AccountPlan]:
        return [account for ou in self.walk() for account in ou.accounts]


def _walk(nodes: list[OuNode]) -> Iterator[OuNode]:
    for node in nodes:
        yield node
        yield from _walk(node.children)
