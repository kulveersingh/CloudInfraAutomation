import pathlib
import re

import pytest

from app.providers.aws.landing_zone.controls import control_identifier
from app.providers.aws.provider import AwsProvider
from tests.lz_factories import CATALOG, answers_dict, edited

APP = pathlib.Path(__file__).resolve().parent.parent / "app"
AWS_SPECIFICS = re.compile(r"AWS::|arn:aws|aws:[A-Z]|\$\{AWS::|from app\.providers\.aws|import boto3|cfnlint|AWS_[A-Z]")
ALEX = {"X-Actor": "alex", "X-Roles": "platform-admin"}


def toolkit():
    return AwsProvider().landing_zone()


def test_aws_landing_zone_repository():
    assert toolkit().repository_name == "landing-zone-infra"


def test_aws_bundle_renders_the_cloudformation_stacks():
    files = toolkit().bundle.render(edited([])[0], CATALOG)
    assert {"stacks/lz-foundation.yaml", "stacks/lz-structure.yaml", "design.json"} <= set(files)


def test_aws_checks_cover_its_limits():
    assert [type(check).__name__ for check in toolkit().checks] == [
        "MaximumDepth", "ScpQuotaCheck", "StackSizeRule"]


def test_aws_advice_covers_registration_limits():
    assert "OuSizeWithinRegistrationLimit" in [type(advice).__name__ for advice in toolkit().advice]


def test_aws_checks_find_nothing_in_the_recommended_design():
    design = edited([])[0]
    assert [problem for check in toolkit().checks for problem in check.problems(design, CATALOG)] == []


def test_control_identifiers_are_global_control_catalog_arns():
    assert control_identifier("abc123") == "arn:aws:controlcatalog:::control/abc123"


def test_landing_zone_for_an_unknown_provider_is_rejected(client):
    response = client.post("/v1/admin/landing-zone:propose",
                           json={"provider": "azure", "answers": answers_dict(), "edits": []}, headers=ALEX)
    assert (response.status_code, response.json()["detail"]) == (422, "Unknown cloud provider 'azure'.")


@pytest.mark.parametrize("package", ["landing_zone"])
def test_core_landing_zone_has_no_aws_specifics(package):
    offenders = [str(path.relative_to(APP)) for path in sorted((APP / package).rglob("*.py"))
                 if AWS_SPECIFICS.search(path.read_text())]
    assert offenders == []
