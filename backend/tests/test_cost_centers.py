import pytest

from app.registry.cost_centers import CostCenter, CostCenterContext, CostCenterFormat, CostCenterResolver

RESOLVER = CostCenterResolver.default()


def context(**overrides) -> CostCenterContext:
    values = {"organization_default": "CC-1000", "portfolio": "CC-4400", "product": "CC-4410",
              "project_override": None}
    values.update(overrides)
    return CostCenterContext(**values)


def test_project_override_wins():
    assert RESOLVER.resolve(context(project_override="CC-9999")) == CostCenter("CC-9999", "project")


def test_product_value_used_next():
    assert RESOLVER.resolve(context()) == CostCenter("CC-4410", "product")


def test_portfolio_value_inherited():
    assert RESOLVER.resolve(context(product=None)) == CostCenter("CC-4400", "portfolio")


def test_organization_default_last():
    assert RESOLVER.resolve(context(product=None, portfolio=None)) == CostCenter("CC-1000", "organization")


def test_empty_strings_count_as_unset():
    assert RESOLVER.resolve(context(product="", portfolio="")).source == "organization"


def test_cost_center_serializes():
    assert CostCenter("CC-1000", "organization").as_dict() == {"value": "CC-1000", "source": "organization"}


@pytest.mark.parametrize(("value", "valid"), [("CC-1234", True), ("cc-1234", False), ("CC-12", False), ("", False)])
def test_format_validation(value, valid):
    assert CostCenterFormat(r"^CC-[0-9]{4}$").is_valid(value) is valid
