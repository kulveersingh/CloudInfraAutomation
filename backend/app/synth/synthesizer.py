import json

from app.synth.binders.registry import BinderRegistry
from app.synth.blocks.base import Block
from app.synth.blocks.registry import BlockRegistry
from app.synth.request import PROJECT_NAME_PATTERN, ProjectRequest
from app.synth.template import Template

ENGINE_VERSION = "0.1.0"
GENERATOR_NAME = "cloudinfra-synth"


class StackFoundation:
    """Parameters and conditions every generated template shares (environment, region role, activation)."""

    PARAMETERS = {
        "ProjectName": {"Type": "String", "AllowedPattern": PROJECT_NAME_PATTERN},
        "EnvironmentName": {"Type": "String"},
        "ResilienceMode": {"Type": "String", "AllowedValues": ["single", "dr", "ha"], "Default": "single"},
        "RegionRole": {"Type": "String", "AllowedValues": ["primary", "secondary"], "Default": "primary"},
        "ActivationState": {"Type": "String", "AllowedValues": ["active", "standby"], "Default": "active"},
    }
    CONDITIONS = {
        "IsActive": {"Fn::Equals": [{"Ref": "ActivationState"}, "active"]},
        "IsPrimary": {"Fn::Equals": [{"Ref": "RegionRole"}, "primary"]},
    }

    def apply(self, template: Template) -> None:
        for name, body in self.PARAMETERS.items():
            template.add_parameter(name, body)
        for name, body in self.CONDITIONS.items():
            template.add_condition(name, body)


class ContractParameter:
    """Publishes the infrastructure contract to SSM so application repos can discover resources."""

    LOGICAL_ID = "ContractParameter"

    def __init__(self, blocks: dict[str, Block]):
        self._blocks = blocks

    def apply(self, template: Template) -> None:
        template.add_resource(self.LOGICAL_ID, {"Type": "AWS::SSM::Parameter", "Properties": {
            "Name": {"Fn::Sub": "/platform/projects/${ProjectName}/contract"},
            "Type": "String",
            "Value": {"Fn::Sub": json.dumps(self._contract(), sort_keys=True)}}})

    def _contract(self) -> dict:
        resources = {resource_id: {"type": block.type_name, **block.contract_entry()}
                     for resource_id, block in self._blocks.items()}
        return {"contractVersion": "1", "project": "${ProjectName}", "environment": "${EnvironmentName}",
                "region": "${AWS::Region}", "regionRole": "${RegionRole}", "activationState": "${ActivationState}",
                "resources": resources}


class TemplateSynthesizer:
    """Turns a validated project request into a CloudFormation template using registered blocks and binders."""

    def __init__(self, blocks: BlockRegistry, binders: BinderRegistry):
        self._block_registry = blocks
        self._binder_registry = binders

    def synthesize(self, request: ProjectRequest) -> dict:
        template = Template()
        template.set_metadata({"Generator": {"name": GENERATOR_NAME, "version": ENGINE_VERSION}})
        StackFoundation().apply(template)
        blocks = {spec.id: self._block_registry.create(spec, request) for spec in request.resources}
        self._bind_connections(request, blocks, template)
        for block in blocks.values():
            self._emit(block, template)
        ContractParameter(blocks).apply(template)
        return template.to_dict()

    def _bind_connections(self, request: ProjectRequest, blocks: dict[str, Block], template: Template) -> None:
        for connection in request.connections:
            binder = self._binder_registry.binder(connection.kind)
            binder.bind(connection, blocks[connection.source], blocks[connection.target], template)

    def _emit(self, block: Block, template: Template) -> None:
        for name, body in block.required_parameters().items():
            template.add_parameter(name, body)
        block.emit(template)
