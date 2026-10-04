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
