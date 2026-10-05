from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models

ORGANIZATION_SETTINGS_ID = 1


class RegistryRepository:
    """Persistence for the org registry, environments, regions, accounts and cost centers."""

    def __init__(self, session: Session):
        self._session = session

    def organization_settings(self) -> models.OrganizationSettings:
        return self._session.get(models.OrganizationSettings, ORGANIZATION_SETTINGS_ID)

    def portfolios(self) -> list[models.Portfolio]:
        return list(self._session.scalars(select(models.Portfolio).order_by(models.Portfolio.id)))

    def portfolio(self, portfolio_id: str) -> models.Portfolio | None:
        return self._session.get(models.Portfolio, portfolio_id)

    def product(self, product_id: str) -> models.Product | None:
        return self._session.get(models.Product, product_id)

    def environments(self) -> list[models.Environment]:
        return list(self._session.scalars(select(models.Environment).order_by(models.Environment.position)))

    def environment(self, environment_id: str) -> models.Environment | None:
        return self._session.get(models.Environment, environment_id)

    def environment_ids(self) -> set[str]:
        return {environment.id for environment in self.environments()}

    def regions(self, provider: str | None = None) -> list[models.Region]:
        query = select(models.Region).order_by(models.Region.provider, models.Region.id)
        if provider is not None:
            query = query.where(models.Region.provider == provider)
        return list(self._session.scalars(query))

    def region(self, provider: str, region_id: str) -> models.Region | None:
        return self._session.get(models.Region, (provider, region_id))

    def account_for(self, provider: str, portfolio_id: str, environment_id: str) -> str | None:
        return self._session.scalar(select(models.AccountBinding.account_id).where(
            models.AccountBinding.provider == provider, models.AccountBinding.portfolio_id == portfolio_id,
            models.AccountBinding.environment_id == environment_id))

    def override_for(self, project_name: str) -> models.CostCenterOverride | None:
        return self._session.get(models.CostCenterOverride, project_name)

    def save_override(self, override: models.CostCenterOverride) -> None:
        self._session.merge(override)

    def add_audit(self, actor: str, action: str, details: dict) -> None:
        self._session.add(models.AuditEntry(actor=actor, action=action, details=details))

    def commit(self) -> None:
        self._session.commit()
