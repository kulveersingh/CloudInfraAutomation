from collections.abc import Iterator
from dataclasses import dataclass, field

from app.landing_zone.answers import LandingZoneAnswers

DOMAIN_KINDS = frozenset({"environment", "infrastructure", "custom_domain"})


@dataclass(frozen=True)
class OrgCatalog:
    """Portfolio and product ids from the registry, used to name accounts."""

    portfolios: list[str]
    products: list[str]


@dataclass(frozen=True)
class AccountPlan:
    """An account to vend. Fixed accounts belong to a questionnaire answer; added ones come from the tree editor."""

    name: str
    email: str | None = None  # AWS accounts have one; Google Cloud projects don't
    fixed: bool = False
    added: bool = False
    enabled: bool = True
    domain: str | None = None

    @property
    def label(self) -> str:
        return self.name if self.enabled else f"{self.name} (disabled)"


@dataclass
class OuNode:
    key: str
    name: str
    kind: str
    environment: str | None = None
    tier: str | None = None
    created_by_service: bool = False  # created by the cloud's landing-zone service, not by the platform
    children: list["OuNode"] = field(default_factory=list)
    accounts: list[AccountPlan] = field(default_factory=list)
    custom: bool = False
    domain: str | None = None

    @property
    def label(self) -> str:
        return f"{self.name} OU"

    @property
    def isolation_domain(self) -> str | None:
        """The environment, Infrastructure or root-level custom OU whose isolation this OU shares."""
        return self.domain or (self.key if self.kind in DOMAIN_KINDS else None)

    def descendants(self) -> list["OuNode"]:
        return list(_walk(self.children))

    def subtree_accounts(self) -> list[AccountPlan]:
        return [account for ou in (self, *self.descendants()) for account in ou.accounts]

    def enabled_accounts(self) -> list[AccountPlan]:
        return [account for account in self.accounts if account.enabled]

    def is_empty(self) -> bool:
        return not self.children and not self.accounts


@dataclass
class LandingZoneDesign:
    """The proposed organization: OU tree with accounts, produced by the designer and adjusted by the tree editor."""

    answers: LandingZoneAnswers
    root_ous: list[OuNode] = field(default_factory=list)
    edit_problems: list[str] = field(default_factory=list)
    edits: list = field(default_factory=list)  # the TreeEdits applied, in order
    provider: str = "aws"
    namer: object = None  # the cloud's UnitNamer, which the tree editor also uses for the units it adds
    units: object = None  # the cloud's UnitCatalog

    def walk(self) -> Iterator[OuNode]:
        yield from _walk(self.root_ous)

    def ou_named(self, name: str) -> OuNode:
        for ou in self.walk():
            if ou.name == name:
                return ou
        raise KeyError(name)

    def environment_ous(self) -> list[OuNode]:
        return [ou for ou in self.walk() if ou.kind == "environment"]

    def isolated_ous(self) -> list[OuNode]:
        """OUs that are their own isolation boundary: environments and root-level custom OUs."""
        return [ou for ou in self.walk() if ou.kind in ("environment", "custom_domain")]

    def walk_accounts(self) -> list[AccountPlan]:
        """Every account in the tree, disabled ones included."""
        return [account for ou in self.walk() for account in ou.accounts]

    def accounts(self) -> list[AccountPlan]:
        """Accounts to vend; disabled accounts stay in the tree but are not created."""
        return [account for ou in self.walk() for account in ou.enabled_accounts()]


def _walk(nodes: list[OuNode]) -> Iterator[OuNode]:
    for node in nodes:
        yield node
        yield from _walk(node.children)
