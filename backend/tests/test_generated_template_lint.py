"""Every generated template variant must pass cfn-lint with no findings at any severity (errors or warnings)."""

import pytest
from cfnlint.api import ManualArgs, lint

from app.synth.render import RepositoryBundle
from app.synth.request import ProjectRequest
from tests.factories import dr_request_dict, request_dict, with_resources
from tests.synth_helpers import synthesize

ALL_CURATED = [
    {"id": "orders", "type": "dynamodb.table"}, {"id": "jobs", "type": "sqs.queue"}]
ALL_CURATED_CONNECTIONS = [
    {"kind": "iam.access", "source": "processor", "target": "orders", "access": "readwrite"},
    {"kind": "iam.access", "source": "processor", "target": "jobs", "access": "write"}]
SCHEMA_DRIVEN = [
    {"id": "alerts", "type": "AWS::SNS::Topic", "config": {"properties": {"DisplayName": "Alerts"}}},
    {"id": "applogs", "type": "AWS::Logs::LogGroup", "config": {"properties": {"RetentionInDays": 90}}},
    {"id": "ledger", "type": "AWS::RDS::DBCluster", "config": {"properties": {
        "Engine": "aurora-postgresql", "MasterUsername": "ledgeradmin", "ManageMasterUserPassword": True,
        "StorageEncrypted": True}}},
]

VARIANTS = {
    "single": request_dict(),
    "single-all-curated": with_resources(*ALL_CURATED, connections=ALL_CURATED_CONNECTIONS),
    "dr-all-curated": {**with_resources(*ALL_CURATED, connections=ALL_CURATED_CONNECTIONS),
                       "resilience": dr_request_dict()["resilience"]},
    "ha": {**request_dict(resources=[{"id": "reader", "type": "lambda.function"},
                                     {"id": "items", "type": "dynamodb.table"}],
                          connections=[{"kind": "iam.access", "source": "reader", "target": "items",
                                        "access": "read"}]),
           "resilience": {"mode": "ha", "primary_region": "us-east-1", "secondary_region": "us-east-2"}},
    "no-network": request_dict(network={"attach_compute": False}),
    "schema-driven": request_dict(resources=SCHEMA_DRIVEN, connections=[]),
}


def findings(payload: dict) -> list[str]:
    files = RepositoryBundle.default().render(ProjectRequest.model_validate(payload), synthesize(payload))
    return [str(match) for match in lint(files["template.yaml"], config=ManualArgs(regions=["us-east-1", "us-east-2"]))]


@pytest.mark.parametrize("variant", VARIANTS)
def test_generated_template_has_no_cfn_lint_findings(variant):
    assert findings(VARIANTS[variant]) == []
