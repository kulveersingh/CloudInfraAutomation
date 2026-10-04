"""Builders for landing zone inputs. Each test changes only what it is about."""

import copy

from app.landing_zone.answers import LandingZoneAnswers
from app.landing_zone.design import OrgCatalog

_BASE_ANSWERS = {
    "organization_name": "acme",
    "management_email": "aws-management@acme.example",
    "home_region": "us-east-1",
    "governed_regions": ["us-east-1", "us-east-2"],
}

CATALOG = OrgCatalog(portfolios=["pf-payments", "pf-retail"], products=["pr-invoicing", "pr-storefront"])


def answers_dict(**overrides) -> dict:
    answers = copy.deepcopy(_BASE_ANSWERS)
    answers.update(copy.deepcopy(overrides))
    return answers


def answers(**overrides) -> LandingZoneAnswers:
    return LandingZoneAnswers.model_validate(answers_dict(**overrides))


def edited(edits: list[dict], **overrides):
    """The designer's proposal with the editor's changes applied; returns the design and the edit problems."""
    from app.landing_zone.designer import LandingZoneDesigner
    from app.landing_zone.edits import TreeEditor

    design = LandingZoneDesigner.default().design(answers(**overrides), CATALOG)
    return design, TreeEditor().apply(design, TreeEditor.parse(edits))


def add_ou(name: str, parent: str | None = "prod") -> dict:
    return {"op": "add_ou", "parent": parent, "name": name}


def add_account(suffix: str, ou: str) -> dict:
    return {"op": "add_account", "ou": ou, "suffix": suffix}


def account_op(op: str, account: str, **fields) -> dict:
    return {"op": op, "account": account, **fields}
