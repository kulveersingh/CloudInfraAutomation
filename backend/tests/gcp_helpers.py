"""Builders for Google Cloud project requests and readers for the Terraform JSON they generate."""

import copy

from app.providers.gcp.provider import GcpProvider
from app.synth.request import ProjectRequest
from tests.factories import request_dict

SINGLE = {"mode": "single", "primary_region": "us-east1", "secondary_region": None}
DR = {"mode": "dr", "primary_region": "us-east1", "secondary_region": "us-east4"}
HA = {"mode": "ha", "primary_region": "us-east1", "secondary_region": "us-east4"}


def gcp_request(resources=None, connections=None, resilience=None, attach=False, **overrides) -> dict:
    payload = request_dict(provider="gcp", resilience=copy.deepcopy(resilience or SINGLE),
                           network={"attach_compute": attach, "selections": {}}, **overrides)
    if resources is not None:
        payload["resources"] = resources
    if connections is not None:
        payload["connections"] = connections
    else:
        payload["connections"] = [{"kind": "event.notify", "source": "uploads", "target": "processor",
                                   "prefix": "incoming/"}] if resources is None else []
    if resources is None:
        payload["resources"] = [{"id": "uploads", "type": "storage.bucket"},
                                {"id": "processor", "type": "compute.function"}]
    return payload


def synthesize(payload: dict) -> dict:
    return GcpProvider().project().synthesizer.synthesize(ProjectRequest.model_validate(payload))


def resource(document: dict, type_name: str, name: str) -> dict:
    return document["resource"][type_name][name]


def members(document: dict, type_name: str) -> list[dict]:
    return list(document["resource"].get(type_name, {}).values())
