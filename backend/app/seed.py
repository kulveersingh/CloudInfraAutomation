import hashlib
from typing import ClassVar

from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import models
from app.db.database import Database
from app.providers.base import DEFAULT_PROVIDER


class ReferenceData:
    """Example registry, environments, regions and accounts used for local development (all invented)."""

    DEFAULT_COST_CENTER = "CC-1000"
    COST_CENTER_PATTERN = "^CC-[0-9]{4}$"
    PORTFOLIOS = (
        ("pf-payments", "Payments", "CC-4400"),
        ("pf-retail", "Retail", "CC-5100"),
        ("pf-data", "Data & Analytics", None),
    )
    PRODUCTS = (
        ("pr-invoicing", "pf-payments", "Invoicing", "product", "CC-4410", "confidential"),
        ("pl-payments-core", "pf-payments", "Payments Core", "platform", None, "restricted"),
        ("pr-storefront", "pf-retail", "Storefront", "product", "CC-5120", "internal"),
        ("pr-loyalty", "pf-retail", "Loyalty", "product", None, "confidential"),
        ("pl-datalake", "pf-data", "Data Lake Platform", "platform", "CC-7000", "confidential"),
    )
    ENVIRONMENTS = (
        ("sandbox", "Sandbox", "sandbox", 1, False),
        ("dev", "DEV", "nonprod", 2, False),
        ("test", "TEST", "nonprod", 3, False),
        ("stage", "QA/STAGE", "nonprod", 4, True),
        ("prod", "PROD", "prod", 5, True),
    )
    REGIONS = (
        ("us-east-1", "US East (N. Virginia)", True),
        ("us-east-2", "US East (Ohio)", True),
        ("us-west-2", "US West (Oregon)", True),
        ("eu-west-1", "Europe (Ireland)", True),
        ("eu-central-1", "Europe (Frankfurt)", True),
        ("ap-southeast-2", "Asia Pacific (Sydney)", False),
    )
    ACCOUNT_PREFIXES: ClassVar[dict[str, tuple[str, ...]]] = {"pf-payments": ("1", "2", "3", "4", "5"), "pf-retail": ("61", "62", "63", "64", "65"),
                        "pf-data": ("71", "72", "73", "74", "66")}

    def objects(self) -> list:
        return [self._organization(), *self._portfolios(), *self._products(), *self._environments(),
                *self._regions()]

    NETWORK_REGIONS = ("us-east-1", "us-east-2")

    def networks(self) -> list[models.Network]:
        accounts = [binding.account_id for binding in self.account_bindings()]
        pairs = [(account, region) for account in accounts for region in self.NETWORK_REGIONS]
        return [self._network(account, region, index) for index, (account, region) in enumerate(pairs, start=1)]

    def _network(self, account_id: str, region: str, index: int) -> models.Network:
        digest = hashlib.sha1(f"{account_id}{region}".encode()).hexdigest()
        return models.Network(
            id=f"net-{account_id}-{region}", name="Org shared VPC", account_id=account_id, region=region,
            network_ref=f"vpc-{digest[:17]}", cidr=f"10.{index}.0.0/16",
            subnet_refs=[f"subnet-{digest[offset:offset + 17]}" for offset in (1, 2, 3)],
            firewall_refs=[f"sg-{digest[4:21]}"], is_default=True)

    def account_bindings(self) -> list[models.AccountBinding]:
        environment_ids = [environment[0] for environment in self.ENVIRONMENTS]
        return [models.AccountBinding(provider=DEFAULT_PROVIDER, environment_id=environment_id,
                                      portfolio_id=portfolio_id,
                                      account_id=prefix.ljust(12, prefix[-1]))
                for portfolio_id, prefixes in self.ACCOUNT_PREFIXES.items()
                for environment_id, prefix in zip(environment_ids, prefixes, strict=True)]

    def _organization(self) -> models.OrganizationSettings:
        return models.OrganizationSettings(id=1, default_cost_center=self.DEFAULT_COST_CENTER,
                                           cost_center_pattern=self.COST_CENTER_PATTERN)

    def _portfolios(self) -> list:
        return [models.Portfolio(id=pid, name=name, cost_center=cc) for pid, name, cc in self.PORTFOLIOS]

    def _products(self) -> list:
        return [models.Product(id=pid, portfolio_id=pf, name=name, kind=kind, cost_center=cc,
                               classification_ceiling=ceiling)
                for pid, pf, name, kind, cc, ceiling in self.PRODUCTS]

    def _environments(self) -> list:
        return [models.Environment(id=eid, name=name, tier=tier, position=position, requires_approval=approval)
                for eid, name, tier, position, approval in self.ENVIRONMENTS]

    def _regions(self) -> list:
        return [models.Region(provider=DEFAULT_PROVIDER, id=rid, name=name, enabled=enabled)
                for rid, name, enabled in self.REGIONS]


class ReferenceDataSeeder:
    """Inserts reference data that is missing; never overwrites values admins have changed."""

    def __init__(self, session: Session, data: ReferenceData | None = None):
        self._session = session
        self._data = data or ReferenceData()

    def seed(self) -> None:
        for item in self._data.objects():
            self._add_if_missing(item)
        self._session.flush()
        for binding in self._data.account_bindings():
            self._add_binding_if_missing(binding)
        for network in self._data.networks():
            self._add_if_missing(network)
        self._session.commit()

    def _add_if_missing(self, item) -> None:
        existing = self._session.get(type(item), inspect(type(item)).primary_key_from_instance(item))
        if existing is None:
            self._session.merge(item)

    def _add_binding_if_missing(self, binding: models.AccountBinding) -> None:
        existing = self._session.scalar(select(models.AccountBinding).where(
            models.AccountBinding.provider == binding.provider,
            models.AccountBinding.environment_id == binding.environment_id,
            models.AccountBinding.portfolio_id == binding.portfolio_id))
        if existing is None:
            self._session.add(binding)


class SeedCommand:
    def __init__(self, settings: Settings):
        self._settings = settings

    def run(self) -> None:
        with Database(self._settings.sqlalchemy_url()).session_factory() as session:
            ReferenceDataSeeder(session).seed()


if __name__ == "__main__":
    SeedCommand(Settings()).run()
