import pytest
from sqlalchemy import delete, select

from app.db import models
from app.errors import NotFoundError, ValidationFailedError
from app.registry.service import RegistryService
from app.synth.request import Resilience


@pytest.fixture
def service(seeded) -> RegistryService:
    return RegistryService.for_session(seeded)


def product_entry(registry: list, portfolio_id: str, product_id: str) -> dict:
    portfolio = next(item for item in registry if item["id"] == portfolio_id)
    return next(item for item in portfolio["products"] if item["id"] == product_id)


def test_registry_lists_portfolios(service):
    assert [item["id"] for item in service.org_registry()] == ["pf-data", "pf-payments", "pf-retail"]


def test_product_cost_center_from_product(service):
    assert product_entry(service.org_registry(), "pf-payments", "pr-invoicing")["cost_center"] == {
        "value": "CC-4410", "source": "product"}


def test_product_cost_center_inherited_from_portfolio(service):
    assert product_entry(service.org_registry(), "pf-payments", "pl-payments-core")["cost_center"] == {
        "value": "CC-4400", "source": "portfolio"}


def test_cost_center_settings(service):
    settings = service.cost_centers()
    assert (settings["default"], settings["pattern"], len(settings["portfolios"])) == (
        "CC-1000", "^CC-[0-9]{4}$", 3)


def test_update_cost_centers_changes_resolution(service):
    service.update_cost_centers({"products": {"pr-invoicing": None}}, actor="alex")
    assert product_entry(service.org_registry(), "pf-payments", "pr-invoicing")["cost_center"]["source"] == \
        "portfolio"


def test_update_default_cost_center(service):
    service.update_cost_centers({"default": "CC-2000"}, actor="alex")
    assert service.cost_centers()["default"] == "CC-2000"


def test_update_portfolio_cost_center(service):
    service.update_cost_centers({"portfolios": {"pf-data": "CC-7100"}}, actor="alex")
    assert product_entry(service.org_registry(), "pf-data", "pl-datalake")["cost_center"]["value"] == "CC-7000"


def test_update_is_audited(service, seeded):
    service.update_cost_centers({"default": "CC-2000"}, actor="alex")
    audit = seeded.scalars(select(models.AuditEntry)).one()
    assert (audit.actor, audit.action) == ("alex", "cost_centers.update")


def test_invalid_cost_center_rejected(service):
    with pytest.raises(ValidationFailedError, match="bad"):
        service.update_cost_centers({"default": "bad"}, actor="alex")


def test_unknown_portfolio_rejected(service):
    with pytest.raises(ValidationFailedError, match="Unknown portfolio 'pf-nope'"):
        service.update_cost_centers({"portfolios": {"pf-nope": "CC-1111"}}, actor="alex")


def test_unknown_product_rejected(service):
    with pytest.raises(ValidationFailedError, match="Unknown product 'pr-nope'"):
        service.update_cost_centers({"products": {"pr-nope": "CC-1111"}}, actor="alex")


def test_project_override_wins(service):
    service.set_project_override("storefront-search", "CC-5199", reason="budget", actor="alex")
    assert service.resolve_cost_center("pf-retail", "pr-storefront", "storefront-search").as_dict() == {
        "value": "CC-5199", "source": "project"}


def test_project_override_can_be_replaced(service):
    service.set_project_override("storefront-search", "CC-5199", reason="budget", actor="alex")
    service.set_project_override("storefront-search", "CC-5198", reason="new budget", actor="alex")
    assert service.resolve_cost_center("pf-retail", "pr-storefront", "storefront-search").value == "CC-5198"


def test_project_override_must_be_valid(service):
    with pytest.raises(ValidationFailedError):
        service.set_project_override("storefront-search", "nope", reason="budget", actor="alex")


def test_resolve_for_unknown_product(service):
    with pytest.raises(NotFoundError):
        service.resolve_cost_center("pf-retail", "pr-nope", "x")


def test_ownership_valid(service):
    assert service.validate_ownership("pf-payments", "pr-invoicing") is None


def test_ownership_product_from_other_portfolio(service):
    with pytest.raises(ValidationFailedError, match="does not belong"):
        service.validate_ownership("pf-payments", "pr-storefront")


def test_ownership_unknown_portfolio(service):
    with pytest.raises(NotFoundError, match="pf-nope"):
        service.validate_ownership("pf-nope", "pr-invoicing")


def test_environments_in_promotion_order(service):
    assert [item["id"] for item in service.environments()] == ["sandbox", "dev", "test", "stage", "prod"]


def test_unknown_environment_rejected(service):
    with pytest.raises(ValidationFailedError, match="Unknown environment 'qa9'"):
        service.validate_environments(["dev", "qa9"])


def test_target_accounts(service):
    assert service.target_accounts("aws", "pf-payments", ["dev", "prod"]) == {"dev": "222222222222", "prod": "555555555555"}


def test_target_account_missing(service, seeded):
    seeded.execute(delete(models.AccountBinding).where(models.AccountBinding.environment_id == "prod"))
    with pytest.raises(ValidationFailedError, match="No account configured"):
        service.target_accounts("aws", "pf-payments", ["prod"])


def test_regions_listed(service):
    assert len(service.regions()) == 6


def test_enable_region(service):
    service.set_region_enabled("aws", "ap-southeast-2", True)
    assert next(item for item in service.regions() if item["id"] == "ap-southeast-2")["enabled"] is True


def test_enable_unknown_region(service):
    with pytest.raises(NotFoundError):
        service.set_region_enabled("aws", "mars-1", True)


def test_enabled_regions_pass(service):
    resilience = Resilience(mode="dr", primary_region="us-east-1", secondary_region="us-east-2")
    assert service.validate_regions("aws", resilience) is None


def test_disabled_region_rejected(service):
    resilience = Resilience(mode="dr", primary_region="us-east-1", secondary_region="ap-southeast-2")
    with pytest.raises(ValidationFailedError, match="ap-southeast-2 is not enabled"):
        service.validate_regions("aws", resilience)


def test_single_region_ignores_secondary(service):
    resilience = Resilience(mode="single", primary_region="us-east-1", secondary_region=None)
    assert service.validate_regions("aws", resilience) is None
