import pytest

from app.landing_zone.catalog.resolver import UNRESOLVED_PREREQUISITE
from app.landing_zone.catalog.templates import TemplateRegistry
from app.landing_zone.validation import DesignAdvisor, DesignValidator
from app.providers.aws.landing_zone.cloudformation.guardrails import GuardrailPlan, ScpQuotaRule
from app.providers.aws.provider import AwsProvider
from tests.lz_factories import CATALOG, edited

TEMPLATES = [template.id for template in TemplateRegistry.default().all()]


def from_template(template_id: str, **overrides):
    template = TemplateRegistry.default().get(template_id)
    return edited(template.edits, **{**template.answers, **overrides})


def environment_names(template_id: str) -> list[str]:
    return [environment.name for environment in from_template(template_id)[0].answers.environments()]


def top_level(template_id: str) -> list[str]:
    return [ou.name for ou in from_template(template_id)[0].root_ous]


@pytest.mark.parametrize("template", TEMPLATES)
def test_every_template_proposes_without_problems(template):
    design, edit_problems = from_template(template)
    problems = [*edit_problems, *DesignValidator.default().problems(design),
                *ScpQuotaRule().problems(GuardrailPlan.for_design(design, CATALOG))]
    assert problems == []


def test_financial_services():
    assert (environment_names("financial-services"), top_level("financial-services")[-1]) == (
        ["Sandbox", "DEV", "TEST", "UAT", "STAGE", "PROD"], "Third-party Integrations")


def test_financial_services_scopes_pci():
    assert [child.name for child in from_template("financial-services")[0].ou_named("PCI").children] == [
        "PCI-STAGE", "PCI-PROD"]


def test_healthcare_renames_uat_to_validation_for_gxp():
    assert environment_names("healthcare") == ["Sandbox", "DEV", "TEST", "VALIDATION", "STAGE", "PROD"]


def test_healthcare_isolates_research():
    assert from_template("healthcare")[0].ou_named("Research").kind == "custom_domain"


def test_public_sector_governs_us_regions():
    assert from_template("public-sector")[0].answers.governed_regions == ["us-east-1", "us-west-2"]


def test_retail_tests_peak_season():
    assert environment_names("retail") == ["Sandbox", "DEV", "QA", "PERF", "STAGE", "PROD"]


def test_saas_has_tenants_under_prod_and_automations():
    design = from_template("saas")[0]
    assert ([child.name for child in design.ou_named("PROD").children], "Automations" in top_level("saas")) == (
        ["Tenants"], True)


def test_eu_sovereignty_stays_in_eu_regions():
    answers = from_template("eu-sovereignty")[0].answers
    assert (answers.home_region, answers.governed_regions, "data-residency" in answers.packs()) == (
        "eu-central-1", ["eu-central-1", "eu-west-1"], True)


# ---- advice that doesn't block approval ----

def warnings(design) -> list[str]:
    return DesignAdvisor([*DesignAdvisor.default().rules, *AwsProvider().landing_zone().advice]).warnings(design)


def test_strict_residency_warns_about_dr_replication():
    design, _ = edited([], control_packs=["foundation", "strict-residency"])
    assert ("Strict residency blocks S3 cross-Region replication, so DR/HA projects in these OUs cannot replicate "
            "S3 buckets.") in warnings(design)


def test_ou_size_near_the_registration_limit_is_flagged():
    design, _ = edited([])
    prod = design.ou_named("PROD")
    prod.accounts = prod.accounts * 501
    assert "OU 'PROD' plans 1002 accounts; AWS Control Tower registers OUs of up to 1000 with 2 governed Regions." in (
        warnings(design))


def test_registration_limit_shrinks_with_many_governed_regions():
    design, _ = edited([])
    design.answers = design.answers.model_copy(update={"governed_regions": [f"r{index}" for index in range(22)]})
    prod = design.ou_named("PROD")
    prod.accounts = prod.accounts * 341
    assert "OU 'PROD' plans 682 accounts; AWS Control Tower registers OUs of up to 680 with 22 governed Regions." in (
        warnings(design))


def test_recommended_design_has_only_the_catalog_refresh_warning():
    assert warnings(edited([])[0]) == [UNRESOLVED_PREREQUISITE]
