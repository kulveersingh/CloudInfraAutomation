"""Builders for Azure project requests and readers for the ARM templates they generate (a data and an app stack)."""

import copy

from app.providers.azure.provider import AzureProvider
from app.synth.request import ProjectRequest
from tests.factories import request_dict

SINGLE = {"mode": "single", "primary_region": "eastus2", "secondary_region": None}
DR = {"mode": "dr", "primary_region": "eastus2", "secondary_region": "centralus"}
HA = {"mode": "ha", "primary_region": "eastus2", "secondary_region": "centralus"}


def azure_request(resources=None, connections=None, resilience=None, attach=False, **overrides) -> dict:
    payload = request_dict(provider="azure", resilience=copy.deepcopy(resilience or SINGLE),
                           network={"attach_compute": attach, "selections": {}}, **overrides)
    if resources is None:
        payload["resources"] = [{"id": "uploads", "type": "storage.bucket"},
                                {"id": "processor", "type": "compute.function"}]
        payload["connections"] = [{"kind": "event.notify", "source": "uploads", "target": "processor",
                                   "prefix": "incoming/", "suffix": ".csv"}] if connections is None else connections
    else:
        payload["resources"] = resources
        payload["connections"] = connections or []
    return payload


def synthesize(payload: dict) -> dict:
    return AzureProvider().project().synthesizer.synthesize(ProjectRequest.model_validate(payload))


def resources(template: dict, type_name: str, service: str | None = None) -> list[dict]:
    """A stack's resources of one type, optionally only those of one service (its `comments`)."""
    return [item for item in template["resources"] if item["type"] == type_name
            and (service is None or item.get("comments") == service)]


def resource(template: dict, type_name: str, service: str) -> dict:
    [found] = resources(template, type_name, service)
    return found
