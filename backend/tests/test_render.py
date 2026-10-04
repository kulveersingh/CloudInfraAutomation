import json
import re

import yaml

from app.synth.lint import CfnLintRunner
from app.synth.render import FileRenderer, RepositoryBundle, TemplateYamlRenderer
from app.synth.request import ProjectRequest
from tests.factories import dr_request_dict, request_dict, with_resources
from tests.synth_helpers import synthesize


def render(payload: dict) -> dict:
    return RepositoryBundle.default().render(ProjectRequest.model_validate(payload), synthesize(payload))


def test_expected_files():
    assert set(render(request_dict())) == {
        "template.yaml", "infra.json", "README.md", ".github/workflows/deploy.yml",
        "config/dev.json", "config/test.json", "config/stage.json", "config/prod.json"}


def test_template_yaml_round_trips():
    assert yaml.safe_load(render(request_dict())["template.yaml"]) == synthesize(request_dict())


def test_infra_json_is_the_request():
    assert json.loads(render(request_dict())["infra.json"]) == ProjectRequest.model_validate(
        request_dict()).model_dump(mode="json")


def test_environment_parameters():
    assert json.loads(render(request_dict())["config/prod.json"]) == {"Parameters": {
        "ProjectName": "invoice-ingest", "EnvironmentName": "prod", "ResilienceMode": "single"}}


def test_workflow_requests_oidc_token():
    assert "id-token: write" in render(request_dict())[".github/workflows/deploy.yml"]


def test_workflow_reads_role_from_variables():
    assert "${{ vars.AWS_ROLE_ARN }}" in render(request_dict())[".github/workflows/deploy.yml"]


def test_workflow_contains_no_account_numbers():
    assert re.search(r"\b\d{12}\b", render(request_dict())[".github/workflows/deploy.yml"]) is None


def test_workflow_tolerates_empty_change_sets():
    assert "--no-fail-on-empty-changeset" in render(request_dict())[".github/workflows/deploy.yml"]


def test_single_region_workflow_has_no_secondary_deploy():
    assert "AWS_SECONDARY_REGION" not in render(request_dict())[".github/workflows/deploy.yml"]


def test_dr_workflow_deploys_standby_region():
    workflow = render(dr_request_dict())[".github/workflows/deploy.yml"]
    assert "${{ vars.AWS_SECONDARY_REGION }}" in workflow and "ActivationState=standby" in workflow


def test_ha_workflow_activates_both_regions():
    payload = request_dict(resilience={"mode": "ha", "primary_region": "us-east-1",
                                       "secondary_region": "us-west-2"})
    assert "ActivationState=standby" not in render(payload)[".github/workflows/deploy.yml"]


def test_readme_names_project_and_product():
    readme = render(request_dict())["README.md"]
    assert "invoice-ingest" in readme and "pr-invoicing" in readme


def test_custom_renderer_extends_bundle():
    class LicenseRenderer(FileRenderer):
        def render(self, request, template) -> dict[str, str]:
            return {"LICENSE": "internal"}

    bundle = RepositoryBundle([LicenseRenderer()])
    assert bundle.render(ProjectRequest.model_validate(request_dict()), {}) == {"LICENSE": "internal"}


def test_generated_template_passes_cfn_lint():
    assert CfnLintRunner().errors(render(request_dict())["template.yaml"]) == []


def test_generated_dr_template_with_all_services_passes_cfn_lint():
    payload = with_resources({"id": "invoices", "type": "dynamodb.table"}, {"id": "jobs", "type": "sqs.queue"},
                             connections=[
                                 {"kind": "iam.access", "source": "processor", "target": "invoices",
                                  "access": "readwrite"},
                                 {"kind": "iam.access", "source": "processor", "target": "jobs", "access": "write"}])
    payload["resilience"] = {"mode": "dr", "primary_region": "us-east-1", "secondary_region": "us-east-2"}
    assert CfnLintRunner().errors(render(payload)["template.yaml"]) == []


def test_template_yaml_never_uses_aliases():
    shared = {"Key": "org:project", "Value": "invoice-ingest"}
    template = {"Resources": {"A": {"Tags": [shared]}, "B": {"Tags": [shared]}}}
    text = TemplateYamlRenderer().render(ProjectRequest.model_validate(request_dict()), template)["template.yaml"]
    assert not re.search(r"[&*]id\d+", text)
