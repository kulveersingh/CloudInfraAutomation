from app.synth.lint import CfnLintRunner
from app.synth.render import RepositoryBundle
from app.synth.request import ProjectRequest
from tests.factories import dr_request_dict, request_dict
from tests.synth_helpers import properties, synthesize

DETACHED = {"attach_compute": False}


def test_network_parameters_are_typed_for_console_dropdowns():
    parameters = synthesize(request_dict())["Parameters"]
    assert ({name: parameters[name]["Type"] for name in ("VpcId", "PrivateSubnetIds", "OrgSecurityGroupIds")} == {
        "VpcId": "AWS::EC2::VPC::Id", "PrivateSubnetIds": "List<AWS::EC2::Subnet::Id>",
        "OrgSecurityGroupIds": "List<AWS::EC2::SecurityGroup::Id>"})


def test_private_cidr_parameter():
    assert synthesize(request_dict())["Parameters"]["OrgPrivateCidr"]["Type"] == "String"


def test_function_runs_in_private_subnets():
    vpc = properties(synthesize(request_dict()), "ProcessorFunction")["VpcConfig"]
    assert vpc["SubnetIds"] == {"Ref": "PrivateSubnetIds"}


def test_function_uses_its_own_and_org_security_groups():
    vpc = properties(synthesize(request_dict()), "ProcessorFunction")["VpcConfig"]
    assert vpc["SecurityGroupIds"] == {"Fn::Split": [",", {"Fn::Join": [",", [
        {"Ref": "ProcessorSecurityGroup"}, {"Fn::Join": [",", {"Ref": "OrgSecurityGroupIds"}]}]]}]}


def test_function_security_group_allows_private_range_and_https():
    group = properties(synthesize(request_dict()), "ProcessorSecurityGroup")
    assert (group["VpcId"], [rule["CidrIp"] for rule in group["SecurityGroupEgress"]]) == (
        {"Ref": "VpcId"}, [{"Ref": "OrgPrivateCidr"}, "0.0.0.0/0"])


def test_function_security_group_has_no_inbound_rules():
    assert "SecurityGroupIngress" not in properties(synthesize(request_dict()), "ProcessorSecurityGroup")


def test_function_role_can_manage_network_interfaces():
    role = properties(synthesize(request_dict()), "ProcessorRole")
    assert role["ManagedPolicyArns"] == [{"Fn::Sub": (
        "arn:${AWS::Partition}:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole")}]


def test_detached_project_has_no_network_parameters():
    assert "VpcId" not in synthesize(request_dict(network=DETACHED))["Parameters"]


def test_detached_function_has_no_vpc_config():
    assert "VpcConfig" not in properties(synthesize(request_dict(network=DETACHED)), "ProcessorFunction")


def test_project_without_compute_has_no_network_parameters():
    payload = request_dict(resources=[{"id": "uploads", "type": "s3.bucket"}], connections=[])
    assert "VpcId" not in synthesize(payload)["Parameters"]


def render_workflow(payload: dict) -> str:
    return RepositoryBundle.default().render(ProjectRequest.model_validate(payload), synthesize(payload))[
        ".github/workflows/deploy.yml"]


def test_workflow_passes_network_variables():
    workflow = render_workflow(request_dict())
    assert all(value in workflow for value in (
        'VpcId="${{ vars.VPC_ID }}"', 'PrivateSubnetIds="${{ vars.PRIVATE_SUBNET_IDS }}"',
        'OrgSecurityGroupIds="${{ vars.ORG_SECURITY_GROUP_IDS }}"', 'OrgPrivateCidr="${{ vars.ORG_PRIVATE_CIDR }}"'))


def test_secondary_region_uses_its_own_network():
    assert 'VpcId="${{ vars.VPC_ID_SECONDARY }}"' in render_workflow(dr_request_dict())


def test_detached_workflow_has_no_network_variables():
    assert "VPC_ID" not in render_workflow(request_dict(network=DETACHED))


def test_networked_template_passes_cfn_lint():
    payload = dr_request_dict()
    files = RepositoryBundle.default().render(ProjectRequest.model_validate(payload), synthesize(payload))
    assert CfnLintRunner().errors(files["template.yaml"]) == []
