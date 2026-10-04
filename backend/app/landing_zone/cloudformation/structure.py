from app.landing_zone.cloudformation.base import StackContext, StackRenderer, export
from app.landing_zone.cloudformation.references import OU_ID_PATTERN, ou_logical_id, pascal
from app.landing_zone.design import OuNode

ARN_PATTERN = r"^arn:aws[0-9a-zA-Z_\-:\/]+$"
CONTROL_BATCH = 10
BASELINE_VERSION = "4.0"


class StructureStack(StackRenderer):
    """OUs, their Control Tower registration and controls, and the organization policies attached to them."""

    name = "lz-structure"
    description = "Landing zone structure: OUs, Control Tower baselines and controls, organization policies."

    def sections(self, context: StackContext) -> dict:
        created = [ou for ou in context.design.walk() if not ou.created_by_control_tower]
        resources: dict = {}
        for ou in created:
            resources[ou_logical_id(ou)] = {"Type": "AWS::Organizations::OrganizationalUnit", "Properties": {
                "Name": ou.name, "ParentId": context.references.parent_id(ou)}}
            resources[f"Baseline{ou_logical_id(ou)}"] = self._baseline(context, ou)
        resources |= self._controls(context)
        resources |= self._policies(context)
        return {"Parameters": self._parameters(), "Resources": resources, "Outputs": self._outputs(context, created)}

    def _parameters(self) -> dict:
        ou = {"Type": "String", "AllowedPattern": OU_ID_PATTERN}
        arn = {"Type": "String", "AllowedPattern": ARN_PATTERN}
        return {"SecurityOuId": {**ou, "Description": "Security OU created by Control Tower"},
                "SandboxOuId": {**ou, "Description": "Sandbox OU created by Control Tower"},
                "ControlTowerBaselineArn": {**arn, "Description": "AWSControlTowerBaseline ARN (ListBaselines)"},
                "IdentityCenterEnabledBaselineArn": {**arn, "Description": "Enabled IdentityCenterBaseline ARN"},
                "BaselineVersion": {"Type": "String", "Default": BASELINE_VERSION}}

    def _baseline(self, context: StackContext, ou: OuNode) -> dict:
        parent = context.references.ancestors(ou)[:-1]
        depends = [f"Baseline{ou_logical_id(parent[-1])}"] if parent and not parent[-1].created_by_control_tower else []
        body = {"Type": "AWS::ControlTower::EnabledBaseline", "Properties": {
            "BaselineIdentifier": {"Ref": "ControlTowerBaselineArn"}, "BaselineVersion": {"Ref": "BaselineVersion"},
            "TargetIdentifier": context.references.arn(ou),
            "Parameters": [{"Key": "IdentityCenterEnabledBaselineArn",
                            "Value": {"Ref": "IdentityCenterEnabledBaselineArn"}}]}}
        return {**body, "DependsOn": depends} if depends else body

    def _controls(self, context: StackContext) -> dict:
        resources: dict = {}
        names: list[str] = []
        for ou in context.design.walk():
            for control in context.guardrails.controls.get(ou.key, []):
                name = f"Control{pascal(ou.key)}{pascal(control.removeprefix('AWS-GR_').lower())}"
                depends = [] if ou.created_by_control_tower else [f"Baseline{ou_logical_id(ou)}"]
                if len(names) >= CONTROL_BATCH:
                    depends.append(names[-CONTROL_BATCH])
                body = {"Type": "AWS::ControlTower::EnabledControl", "Properties": {
                    "ControlIdentifier": {"Fn::Sub": f"arn:aws:controltower:${{AWS::Region}}::control/{control}"},
                    "TargetIdentifier": context.references.arn(ou)}}
                resources[name] = {**body, "DependsOn": depends} if depends else body
                names.append(name)
        return resources

    def _policies(self, context: StackContext) -> dict:
        root = context.references.exports.value("RootId")
        return {f"Policy{pascal(policy.name.removeprefix(context.design.answers.organization_name + '-'))}": {
            "Type": "AWS::Organizations::Policy", "Properties": {
                "Name": policy.name, "Type": policy.type, "Content": policy.content,
                "TargetIds": [root if ou is None else context.references.id(ou) for ou in policy.targets]}}
            for policy in context.guardrails.policies}

    def _outputs(self, context: StackContext, created: list[OuNode]) -> dict:
        outputs = {}
        for ou in created:
            logical = ou_logical_id(ou)
            outputs[f"{logical}Id"] = export(context, f"{logical}Id", {"Ref": logical})
            outputs[f"{logical}Arn"] = export(context, f"{logical}Arn", {"Fn::GetAtt": [logical, "Arn"]})
        return outputs
