"""Helpers for reading synthesized templates in tests."""

from app.synth.binders.registry import BinderRegistry
from app.synth.blocks.registry import BlockRegistry
from app.synth.request import ProjectRequest
from app.synth.synthesizer import TemplateSynthesizer


def synthesize(payload: dict) -> dict:
    synthesizer = TemplateSynthesizer(BlockRegistry.default(), BinderRegistry.default())
    return synthesizer.synthesize(ProjectRequest.model_validate(payload))


def resource(template: dict, logical_id: str) -> dict:
    return template["Resources"][logical_id]


def properties(template: dict, logical_id: str) -> dict:
    return resource(template, logical_id)["Properties"]


def statements_by_sid(policy_document: dict) -> dict:
    return {statement["Sid"]: statement for statement in policy_document["Statement"]}


def role_statements(template: dict, role_id: str) -> list:
    return properties(template, role_id)["Policies"][0]["PolicyDocument"]["Statement"]


def _references(node, found: set) -> set:
    if isinstance(node, dict):
        if "Ref" in node and isinstance(node["Ref"], str):
            found.add(node["Ref"])
        if "Fn::GetAtt" in node:
            found.add(node["Fn::GetAtt"][0])
        for value in node.values():
            _references(value, found)
    elif isinstance(node, list):
        for value in node:
            _references(value, found)
    return found


def dependency_graph(template: dict) -> dict:
    resources = template["Resources"]
    graph = {}
    for logical_id, body in resources.items():
        depends = body.get("DependsOn", [])
        edges = set(depends if isinstance(depends, list) else [depends])
        edges |= _references(body.get("Properties", {}), set())
        graph[logical_id] = {edge for edge in edges if edge in resources}
    return graph


def has_cycle(graph: dict) -> bool:
    visiting, done = set(), set()

    def visit(node) -> bool:
        if node in done:
            return False
        if node in visiting:
            return True
        visiting.add(node)
        cyclic = any(visit(edge) for edge in graph[node])
        visiting.discard(node)
        done.add(node)
        return cyclic

    return any(visit(node) for node in graph)
