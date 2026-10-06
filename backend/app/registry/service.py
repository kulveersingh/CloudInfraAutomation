from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import models
from app.errors import NotFoundError, ValidationFailedError
from app.registry.cost_centers import CostCenter, CostCenterContext, CostCenterFormat, CostCenterResolver
from app.registry.repository import RegistryRepository
from app.synth.request import Resilience


class CostCenterChange(BaseModel):
    default: str | None = None
    portfolios: dict[str, str | None] = Field(default_factory=dict)
    products: dict[str, str | None] = Field(default_factory=dict)

    def submitted_values(self) -> list[str | None]:
        defaults = [self.default] if "default" in self.model_fields_set else []
        assigned = [value for value in [*self.portfolios.values(), *self.products.values()] if value is not None]
        return defaults + assigned


def require(item, error: Exception):
    if item is None:
        raise error
    return item


class RegistryService:
    """Org registry use cases: ownership, cost centers, environments, regions and target accounts."""

    def __init__(self, repository: RegistryRepository, resolver: CostCenterResolver):
        self._repository = repository
        self._resolver = resolver

    @classmethod
    def for_session(cls, session: Session) -> "RegistryService":
        return cls(RegistryRepository(session), CostCenterResolver.default())

    # ---- registry ----

    def org_registry(self) -> list[dict]:
        settings = self._repository.organization_settings()
        return [self._portfolio_entry(portfolio, settings) for portfolio in self._repository.portfolios()]

    def validate_ownership(self, portfolio_id: str, product_id: str) -> None:
        portfolio = self._portfolio(portfolio_id)
        product = self._product(product_id)
        if product.portfolio_id != portfolio.id:
            raise ValidationFailedError(f"Product '{product_id}' does not belong to portfolio '{portfolio_id}'.")

    # ---- cost centers ----

    def cost_centers(self) -> dict:
        settings = self._repository.organization_settings()
        return {"default": settings.default_cost_center, "pattern": settings.cost_center_pattern,
                "portfolios": [self._cost_center_entry(portfolio, settings)
                               for portfolio in self._repository.portfolios()]}

    def update_cost_centers(self, change, actor: str) -> dict:
        change = CostCenterChange.model_validate(change)
        settings = self._repository.organization_settings()
        self._validate_values(settings, change.submitted_values())
        portfolios = {pid: self._known(self._repository.portfolio(pid), "portfolio", pid) for pid in change.portfolios}
        products = {pid: self._known(self._repository.product(pid), "product", pid) for pid in change.products}
        if "default" in change.model_fields_set:
            settings.default_cost_center = change.default
        for portfolio_id, portfolio in portfolios.items():
            portfolio.cost_center = change.portfolios[portfolio_id]
        for product_id, product in products.items():
            product.cost_center = change.products[product_id]
        self._repository.add_audit(actor, "cost_centers.update", change.model_dump(exclude_unset=True))
        self._repository.commit()
        return self.cost_centers()

    def set_project_override(self, project_name: str, cost_center: str, reason: str, actor: str) -> None:
        self._validate_values(self._repository.organization_settings(), [cost_center])
        self._repository.save_override(models.CostCenterOverride(project_name=project_name, cost_center=cost_center,
                                                                 reason=reason, approved_by=actor))
        self._repository.add_audit(actor, "cost_centers.override", {"project": project_name, "value": cost_center})
        self._repository.commit()

    def resolve_cost_center(self, portfolio_id: str, product_id: str, project_name: str) -> CostCenter:
        portfolio = self._portfolio(portfolio_id)
        product = self._product(product_id)
        override = self._repository.override_for(project_name)
        settings = self._repository.organization_settings()
        return self._resolve(settings, portfolio.cost_center, product.cost_center,
                             override.cost_center if override else None)

    # ---- environments, accounts, regions ----

    def bind_account(self, provider: str, portfolio_id: str, environment_id: str, account_id: str) -> None:
        """A landing zone vended this unit for the portfolio's environment (§20.7, §22.10.6)."""
        self._repository.bind_account(provider, portfolio_id, environment_id, account_id)

    def environments(self) -> list[dict]:
        return [{"id": env.id, "name": env.name, "tier": env.tier, "position": env.position,
                 "requires_approval": env.requires_approval} for env in self._repository.environments()]

    def validate_environments(self, environment_ids: list[str]) -> None:
        known = self._repository.environment_ids()
        problems = [f"Unknown environment '{env}'." for env in environment_ids if env not in known]
        if problems:
            raise ValidationFailedError(" ".join(problems))

    def target_accounts(self, provider: str, portfolio_id: str, environment_ids: list[str]) -> dict[str, str]:
        accounts = {env: self._repository.account_for(provider, portfolio_id, env) for env in environment_ids}
        missing = [env for env, account in accounts.items() if account is None]
        if missing:
            raise ValidationFailedError(f"No account configured for {', '.join(missing)} in '{portfolio_id}'.")
        return accounts

    def regions(self, provider: str | None = None) -> list[dict]:
        return [self._region_entry(region) for region in self._repository.regions(provider)]

    def set_region_enabled(self, provider: str, region_id: str, enabled: bool) -> dict:
        region = require(self._repository.region(provider, region_id),
                         NotFoundError(f"Unknown region '{region_id}' for {provider}."))
        region.enabled = enabled
        self._repository.commit()
        return self._region_entry(region)

    def validate_regions(self, provider: str, resilience: Resilience) -> None:
        disabled = [region for region in resilience.selected_regions() if not self._region_enabled(provider, region)]
        if disabled:
            raise ValidationFailedError(" ".join(f"Region {region} is not enabled." for region in disabled))

    # ---- helpers ----

    def _portfolio(self, portfolio_id: str) -> models.Portfolio:
        return require(self._repository.portfolio(portfolio_id), NotFoundError(f"Unknown portfolio '{portfolio_id}'."))

    def _product(self, product_id: str) -> models.Product:
        return require(self._repository.product(product_id), NotFoundError(f"Unknown product '{product_id}'."))

    def _known(self, item, kind: str, item_id: str):
        return require(item, ValidationFailedError(f"Unknown {kind} '{item_id}'."))

    def _validate_values(self, settings: models.OrganizationSettings, values: list[str | None]) -> None:
        cost_center_format = CostCenterFormat(settings.cost_center_pattern)
        invalid = [value for value in values if not cost_center_format.is_valid(value or "")]
        if invalid:
            raise ValidationFailedError(" ".join(
                f"Invalid cost center '{value}': must match {cost_center_format.pattern}." for value in invalid))

    def _resolve(self, settings, portfolio_value, product_value, override_value) -> CostCenter:
        return self._resolver.resolve(CostCenterContext(organization_default=settings.default_cost_center,
                                                        portfolio=portfolio_value, product=product_value,
                                                        project_override=override_value))

    def _portfolio_entry(self, portfolio: models.Portfolio, settings) -> dict:
        return {"id": portfolio.id, "name": portfolio.name,
                "cost_center": self._resolve(settings, portfolio.cost_center, None, None).as_dict(),
                "products": [self._product_entry(portfolio, product, settings) for product in portfolio.products]}

    def _product_entry(self, portfolio, product: models.Product, settings) -> dict:
        return {"id": product.id, "name": product.name, "kind": product.kind,
                "classification_ceiling": product.classification_ceiling,
                "cost_center": self._resolve(settings, portfolio.cost_center, product.cost_center, None).as_dict()}

    def _cost_center_entry(self, portfolio: models.Portfolio, settings) -> dict:
        return {"id": portfolio.id, "name": portfolio.name, "cost_center": portfolio.cost_center,
                "effective": self._resolve(settings, portfolio.cost_center, None, None).as_dict(),
                "products": [{"id": product.id, "name": product.name, "cost_center": product.cost_center,
                              "effective": self._resolve(settings, portfolio.cost_center, product.cost_center,
                                                         None).as_dict()} for product in portfolio.products]}

    def _region_entry(self, region: models.Region) -> dict:
        return {"provider": region.provider, "id": region.id, "name": region.name, "enabled": region.enabled}

    def _region_enabled(self, provider: str, region_id: str) -> bool:
        region = self._repository.region(provider, region_id)
        return region is not None and region.enabled
