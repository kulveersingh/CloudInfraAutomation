import json
from typing import ClassVar

from app.providers.aws.project.template import Template
from app.synth.blocks.base import Block
from app.synth.request import PROJECT_NAME_PATTERN
from app.synth.synthesizer import ENGINE_VERSION, GENERATOR_NAME, IacDialect


class StackFoundation:
    """Parameters and conditions every generated template shares (environment, region role, activation)."""

    PARAMETERS: ClassVar[dict[str, dict]] = {
        "ProjectName": {"Type": "String", "AllowedPattern": PROJECT_NAME_PATTERN},
        "EnvironmentName": {"Type": "String"},
        "ResilienceMode": {"Type": "String", "AllowedValues": ["single", "dr", "ha"], "Default": "single"},
        "RegionRole": {"Type": "String", "AllowedValues": ["primary", "secondary"], "Default": "primary"},
        "ActivationState": {"Type": "String", "AllowedValues": ["active", "standby"], "Default": "active"},
    }
    CONDITIONS: ClassVar[dict[str, dict]] = {
        "IsActive": {"Fn::Equals": [{"Ref": "ActivationState"}, "active"]},
        "IsPrimary": {"Fn::Equals": [{"Ref": "RegionRole"}, "primary"]},
    }

    def apply(self, template: Template) -> None:
        for name, body in self.PARAMETERS.items():
            template.add_parameter(name, body)
        for name, body in self.CONDITIONS.items():
            template.add_condition(name, body)


class NetworkParameters:
    """Typed parameters (shown as dropdowns in the CloudFormation console) for the organization network."""

    PARAMETERS: ClassVar[dict[str, dict]] = {
        "VpcId": {"Type": "AWS::EC2::VPC::Id", "Description": "Organization VPC for this account and region"},
        "PrivateSubnetIds": {"Type": "List<AWS::EC2::Subnet::Id>", "Description": "Private subnets (two or more AZs)"},
        "OrgSecurityGroupIds": {"Type": "List<AWS::EC2::SecurityGroup::Id>",
                                "Description": "Organization security groups attached to all compute"},
        "OrgPrivateCidr": {"Type": "String", "Default": "10.0.0.0/8",
                           "AllowedPattern": r"^(\d{1,3}\.){3}\d{1,3}/\d{1,2}$",
                           "Description": "Private range reachable from compute"},
    }

    def apply(self, template: Template) -> None:
        for name, body in self.PARAMETERS.items():
            template.add_parameter(name, body)


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
                "region": "${AWS::Region}", "resilienceMode": "${ResilienceMode}", "regionRole": "${RegionRole}", "activationState": "${ActivationState}",
                "resources": resources}


class CloudFormationDialect(IacDialect):
    """AWS documents are CloudFormation templates: shared parameters and conditions, typed network parameters when
    compute joins the organization network, and the infrastructure contract published to SSM."""

    def start(self, request):
        template = Template()
        template.set_metadata({"Generator": {"name": GENERATOR_NAME, "version": ENGINE_VERSION}})
        StackFoundation().apply(template)
        return template

    def add_block(self, document, block):
        for name, body in block.required_parameters().items():
            document.add_parameter(name, body)
        block.emit(document)

    def finish(self, document, request, blocks):
        if any(block.uses_network for block in blocks.values()):
            NetworkParameters().apply(document)
        ContractParameter(blocks).apply(document)
        return document.to_dict()
