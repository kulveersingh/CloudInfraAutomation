"""Builders for test inputs. Each test changes only what it is about."""

import copy

TEST_DATABASE_URL = "postgresql+psycopg://cloudinfra:cloudinfra@localhost:5432/cloudinfra_test"

_BASE_REQUEST = {
    "project_name": "invoice-ingest",
    "ownership": {
        "portfolio_id": "pf-payments",
        "product_id": "pr-invoicing",
        "data_classification": "confidential",
    },
    "resilience": {"mode": "single", "primary_region": "us-east-1", "secondary_region": None},
    "environments": ["dev", "test", "stage", "prod"],
    "resources": [
        {"id": "uploads", "type": "s3.bucket"},
        {"id": "processor", "type": "lambda.function"},
    ],
    "connections": [
        {"kind": "event.notify", "source": "uploads", "target": "processor", "prefix": "incoming/"},
    ],
}


def request_dict(**overrides) -> dict:
    request = copy.deepcopy(_BASE_REQUEST)
    request.update(copy.deepcopy(overrides))
    return request


def dr_request_dict(**overrides) -> dict:
    resilience = {"mode": "dr", "primary_region": "us-east-1", "secondary_region": "us-east-2"}
    return request_dict(resilience=resilience, **overrides)


def with_resources(*extra: dict, connections: list | None = None) -> dict:
    request = request_dict()
    request["resources"].extend(extra)
    if connections is not None:
        request["connections"] = request["connections"] + connections
    return request
