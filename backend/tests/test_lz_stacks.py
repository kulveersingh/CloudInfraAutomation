import json

import pytest
import yaml
from cfnlint.api import ManualArgs, lint

from app.landing_zone.cloudformation.bundle import STACK_FILES, LandingZoneBundle
from app.landing_zone.cloudformation.guardrails import GuardrailPlan, ScpQuotaRule
from app.landing_zone.designer import LandingZoneDesigner
from tests.lz_factories import CATALOG, account_op, add_account, add_ou, answers, edited

FLOW = {"source": "dev", "destination": "test", "protocol": "tcp", "port": 5432, "reason": "Data refresh"}
VARIANTS = {
    "default": {},
    "everything": {"environment_count": 6, "grouping": "prod_nonprod", "compliance": ["PCI", "HIPAA"],
                   "infrastructure": ["network", "shared_services", "identity", "backup", "monitoring", "cicd"],
                   "optional_ous": ["exceptions", "suspended", "individual_business_users"],
                   "controls_profile": "regulated", "network": {"flows": [FLOW]}},
    "four-environments-baseline": {"environment_count": 4, "controls_profile": "baseline",
                                   "sandbox": {"model": "developer"}},
    "local-egress": {"network": {"egress": "local"}},
    "no-inspection": {"network": {"inspection": False}},
    "no-hub": {"infrastructure": ["shared_services"], "network": {"hub": False}},
    "no-shared-accounts": {"infrastructure": [], "network": {"hub": False}},
}


EDITS = [add_ou("Data Lab", parent=None), add_account("data-lab", "custom_data_lab"), add_ou("Payments"),
         account_op("move_account", "acme-payments-prod", ou="custom_payments"),
         account_op("disable_account", "acme-retail-prod")]


def bundle(edits: list[dict] | None = None, **overrides) -> dict[str, str]:
    design = edited(edits or [], **overrides)[0]
    return LandingZoneBundle.default().render(design, CATALOG)


def stack(name: str, edits: list[dict] | None = None, **overrides) -> dict:
    return yaml.safe_load(bundle(edits, **overrides)[STACK_FILES[name]])


def resources(template: dict, type_name: str) -> dict:
    return {key: body for key, body in template["Resources"].items() if body["Type"] == type_name}


def properties(template: dict, logical_id: str) -> dict:
    return template["Resources"][logical_id]["Properties"]


def policy_named(template: dict, name: str) -> dict:
    return next(body["Properties"] for body in resources(template, "AWS::Organizations::Policy").values()
                if body["Properties"]["Name"] == name)


# ---- schema compliance: every stack of every variant passes cfn-lint with no findings ----

@pytest.mark.parametrize("variant", VARIANTS)
@pytest.mark.parametrize("name", list(STACK_FILES))
def test_stack_has_no_cfn_lint_findings(variant, name):
    text = bundle(**VARIANTS[variant])[STACK_FILES[name]]
    assert [str(match) for match in lint(text, config=ManualArgs(regions=["us-east-1", "us-east-2"]))] == []


@pytest.mark.parametrize("name", list(STACK_FILES))
def test_edited_stack_has_no_cfn_lint_findings(name):
    text = bundle(EDITS)[STACK_FILES[name]]
    assert [str(match) for match in lint(text, config=ManualArgs(regions=["us-east-1", "us-east-2"]))] == []


# ---- bundle ----

def test_bundle_files():
    assert set(bundle()) == {*STACK_FILES.values(), "design.json", "README.md", "docs/ou-structure.svg",
                             "docs/ou-structure.mmd", "scripts/apply.sh", ".github/workflows/deploy-landing-zone.yml"}


def test_design_json_records_the_answers():
    assert json.loads(bundle()["design.json"])["answers"]["organization_name"] == "acme"


def test_workflow_runs_the_apply_script_with_oidc():
    workflow = bundle()[".github/workflows/deploy-landing-zone.yml"]
    assert ("id-token: write" in workflow, "./scripts/apply.sh" in workflow) == (True, True)


def test_workflow_requires_the_reviewed_environment():
    assert "environment: management" in bundle()[".github/workflows/deploy-landing-zone.yml"]


def test_apply_script_enables_policy_types_before_the_structure_stack():
    script = bundle()["scripts/apply.sh"]
    assert script.index("enable-policy-type") < script.index("lz-structure")


def test_apply_script_deploys_the_stacks_in_order():
    script = bundle()["scripts/apply.sh"]
    positions = [script.index(f"stacks/{name}.yaml") for name in STACK_FILES]
    assert positions == sorted(positions)


def test_every_deploy_uploads_its_template_to_s3_because_large_stacks_exceed_51200_bytes():
    deploys = [line for line in bundle()["scripts/apply.sh"].splitlines() if "aws cloudformation deploy" in line]
    assert len(deploys) == 5 and all('--s3-bucket "$(template_bucket' in line for line in deploys)


def test_template_bucket_is_private_and_encrypted():
    script = bundle()["scripts/apply.sh"]
    assert "put-public-access-block" in script and "put-bucket-encryption" in script


def test_apply_script_assumes_the_network_account_role():
    assert "role/AWSControlTowerExecution" in bundle()["scripts/apply.sh"]


def test_without_network_or_shared_services_the_vpcs_stay_in_the_management_account():
    script = bundle(infrastructure=[], network={"hub": False})["scripts/apply.sh"]
    assert "AWSControlTowerExecution" not in script and "live in the management account" in script


def test_apply_script_deploys_the_network_in_every_governed_region():
    assert 'for region in us-east-1 us-east-2; do' in bundle()["scripts/apply.sh"]


# ---- foundation ----

def test_foundation_creates_the_organization_and_keeps_it():
    organization = next(iter(resources(stack("lz-foundation"), "AWS::Organizations::Organization").values()))
    assert (organization["Properties"]["FeatureSet"], organization["DeletionPolicy"]) == ("ALL", "Retain")


def test_foundation_creates_log_archive_and_audit_accounts():
    names = [body["Properties"]["AccountName"]
             for body in resources(stack("lz-foundation"), "AWS::Organizations::Account").values()]
    assert names == ["acme-log-archive", "acme-audit"]


def test_landing_zone_manifest_governs_the_chosen_regions():
    manifest = properties(stack("lz-foundation"), "LandingZone")["Manifest"]
    assert manifest["governedRegions"] == ["us-east-1", "us-east-2"]


def test_landing_zone_manifest_names_security_and_sandbox_ous():
    manifest = properties(stack("lz-foundation", environment_names={"sandbox": "Playground"}), "LandingZone")["Manifest"]
    assert manifest["organizationStructure"] == {"security": {"name": "Security"}, "sandbox": {"name": "Playground"}}


def test_landing_zone_manifest_keeps_logs_for_the_chosen_retention():
    manifest = properties(stack("lz-foundation", log_retention_days=730), "LandingZone")["Manifest"]
    assert manifest["centralizedLogging"]["configurations"]["loggingBucket"]["retentionDays"] == 730


def test_landing_zone_enables_identity_center_access():
    assert properties(stack("lz-foundation"), "LandingZone")["Manifest"]["accessManagement"] == {"enabled": True}


def test_control_tower_prerequisite_roles():
    roles = [body["Properties"]["RoleName"] for body in resources(stack("lz-foundation"), "AWS::IAM::Role").values()]
    assert roles == ["AWSControlTowerAdmin", "AWSControlTowerCloudTrailRole", "AWSControlTowerStackSetRole",
                     "AWSControlTowerConfigAggregatorRoleForOrganizations"]


# ---- structure: OUs, baselines, controls ----

def test_structure_creates_the_ous_control_tower_does_not():
    names = [body["Properties"]["Name"]
             for body in resources(stack("lz-structure"), "AWS::Organizations::OrganizationalUnit").values()]
    assert names == ["Infrastructure", "DEV", "TEST", "STAGE", "PROD", "Policy Staging", "Exceptions", "Suspended"]


def test_control_tower_ous_come_in_as_parameters():
    assert {"SecurityOuId", "SandboxOuId"} <= set(stack("lz-structure")["Parameters"])


def test_nested_ous_reference_their_parent():
    assert properties(stack("lz-structure", grouping="prod_nonprod"), "OuProd")["ParentId"] == {"Ref": "OuParentProd"}


def test_top_level_ous_hang_off_the_root():
    assert properties(stack("lz-structure"), "OuProd")["ParentId"] == {"Fn::ImportValue": "acme-lz-RootId"}


def test_every_created_ou_is_registered_with_control_tower():
    template = stack("lz-structure")
    registered = [body["Properties"]["TargetIdentifier"]
                  for body in resources(template, "AWS::ControlTower::EnabledBaseline").values()]
    assert {"Fn::GetAtt": ["OuProd", "Arn"]} in registered and len(registered) == 8


def test_child_ou_registration_waits_for_its_parent():
    template = stack("lz-structure", grouping="prod_nonprod")
    assert "BaselineOuParentProd" in template["Resources"]["BaselineOuProd"]["DependsOn"]


def controls_on(template: dict, logical_ou: str) -> list[str]:
    return [body["Properties"]["ControlIdentifier"]["Fn::Sub"].rsplit("/", 1)[-1]
            for body in resources(template, "AWS::ControlTower::EnabledControl").values()
            if body["Properties"]["TargetIdentifier"] == {"Fn::GetAtt": [logical_ou, "Arn"]}]


def test_recommended_controls_on_prod():
    assert {"AWS-GR_RESTRICT_ROOT_USER", "AWS-GR_S3_BUCKET_PUBLIC_READ_PROHIBITED", "AWS-GR_RESTRICTED_SSH"} <= set(
        controls_on(stack("lz-structure"), "OuProd"))


def test_baseline_profile_has_fewer_controls():
    assert controls_on(stack("lz-structure", controls_profile="baseline"), "OuDev") == [
        "AWS-GR_RESTRICT_ROOT_USER", "AWS-GR_RESTRICT_ROOT_USER_ACCESS_KEYS"]


def test_sandbox_controls_target_the_control_tower_ou():
    targets = [body["Properties"]["TargetIdentifier"]
               for body in resources(stack("lz-structure"), "AWS::ControlTower::EnabledControl").values()]
    assert {"Fn::Sub": "arn:aws:organizations::${AWS::AccountId}:ou/${OrgId}/${SandboxOuId}",
            } in [{"Fn::Sub": target["Fn::Sub"][0]} for target in targets if "Fn::Sub" in target]


def test_controls_wait_for_their_ou_registration():
    template = stack("lz-structure")
    control = next(key for key, body in resources(template, "AWS::ControlTower::EnabledControl").items()
                   if body["Properties"]["TargetIdentifier"] == {"Fn::GetAtt": ["OuProd", "Arn"]})
    assert "BaselineOuProd" in template["Resources"][control]["DependsOn"]


def test_controls_are_applied_in_batches():
    template = stack("lz-structure")
    controls = list(resources(template, "AWS::ControlTower::EnabledControl"))
    assert controls[0] in template["Resources"][controls[10]]["DependsOn"]


def test_structure_exports_ou_ids_and_arns():
    outputs = stack("lz-structure")["Outputs"]
    assert (outputs["OuProdId"]["Export"]["Name"], outputs["OuProdArn"]["Export"]["Name"]) == (
        "acme-lz-OuProdId", "acme-lz-OuProdArn")


# ---- structure: organization policies ----

def test_each_environment_ou_gets_its_own_isolation_scp():
    policy = policy_named(stack("lz-structure"), "acme-isolation-prod")
    assert (policy["Type"], policy["TargetIds"]) == ("SERVICE_CONTROL_POLICY", [{"Ref": "OuProd"}])


def test_isolation_scp_denies_role_assumption_outside_the_environment_path():
    statement = policy_named(stack("lz-structure"), "acme-isolation-prod")["Content"]["Statement"][0]
    assert statement["Condition"]["ForAllValues:StringNotLike"]["aws:ResourceOrgPaths"] == {
        "Fn::Sub": ["${OrgId}/${RootId}/${OuProd}/*", {"OrgId": {"Fn::ImportValue": "acme-lz-OrganizationId"},
                                                        "RootId": {"Fn::ImportValue": "acme-lz-RootId"}}]}


def test_isolation_path_includes_parent_ous():
    statement = policy_named(stack("lz-structure", grouping="prod_nonprod"), "acme-isolation-prod")["Content"]["Statement"][0]
    assert statement["Condition"]["ForAllValues:StringNotLike"]["aws:ResourceOrgPaths"]["Fn::Sub"][0] == (
        "${OrgId}/${RootId}/${OuParentProd}/${OuProd}/*")


def test_each_environment_ou_gets_a_resource_control_policy():
    policy = policy_named(stack("lz-structure"), "acme-resource-perimeter-test")
    assert (policy["Type"], policy["Content"]["Statement"][0]["Principal"]) == ("RESOURCE_CONTROL_POLICY", "*")


def test_resource_perimeter_allows_security_and_infrastructure_principals():
    allowed = policy_named(stack("lz-structure"), "acme-resource-perimeter-test")["Content"]["Statement"][0][
        "Condition"]["ForAllValues:StringNotLike"]["aws:PrincipalOrgPaths"]
    assert [path["Fn::Sub"][0] for path in allowed] == [
        "${OrgId}/${RootId}/${OuTest}/*", "${OrgId}/${RootId}/${SecurityOuId}/*", "${OrgId}/${RootId}/${OuInfrastructure}/*"]


def test_baseline_scp_attaches_to_every_environment_ou_when_kept_separate():
    targets = policy_named(stack("lz-structure"), "acme-workload-baseline")["TargetIds"]
    assert targets == [{"Ref": "SandboxOuId"}, {"Ref": "OuDev"}, {"Ref": "OuTest"}, {"Ref": "OuStage"},
                       {"Ref": "OuProd"}, {"Ref": "OuPolicyStaging"}, {"Ref": "OuExceptions"}]


def test_baseline_scp_attaches_to_parents_when_grouped():
    targets = policy_named(stack("lz-structure", grouping="prod_nonprod"), "acme-workload-baseline")["TargetIds"]
    assert {"Ref": "OuParentProd"} in targets and {"Ref": "OuProd"} not in targets


def test_baseline_scp_denies_regions_outside_governance():
    statement = next(item for item in policy_named(stack("lz-structure"), "acme-workload-baseline")["Content"]["Statement"]
                     if item["Sid"] == "DenyUngovernedRegions")
    assert statement["Condition"]["StringNotEquals"]["aws:RequestedRegion"] == ["us-east-1", "us-east-2"]


def test_production_tier_ous_are_protected_from_deletion():
    targets = policy_named(stack("lz-structure"), "acme-production-protection")["TargetIds"]
    assert targets == [{"Ref": "OuStage"}, {"Ref": "OuProd"}]


def test_sandbox_limits_attach_to_the_sandbox_ou():
    assert policy_named(stack("lz-structure"), "acme-sandbox-limits")["TargetIds"] == [{"Ref": "SandboxOuId"}]


def test_suspended_ou_denies_everything_but_break_glass():
    statement = policy_named(stack("lz-structure"), "acme-suspended-deny-all")["Content"]["Statement"][0]
    assert (statement["Action"], statement["Condition"]["ArnNotLike"]["aws:PrincipalARN"]) == (
        "*", ["arn:aws:iam::*:role/BreakGlass", "arn:aws:iam::*:role/AWSControlTowerExecution"])


def test_tag_policy_lists_registry_values_at_the_root():
    policy = policy_named(stack("lz-structure"), "acme-tag-policy")
    assert (policy["TargetIds"], policy["Content"]["tags"]["org:portfolio"]["tag_value"]["@@assign"]) == (
        [{"Fn::ImportValue": "acme-lz-RootId"}], ["pf-payments", "pf-retail"])


def test_backup_policy_copies_to_the_second_region():
    policy = policy_named(stack("lz-structure"), "acme-backup-production")
    rule = policy["Content"]["plans"]["daily"]["rules"]["daily"]
    assert list(rule["copy_actions"]) == ["arn:aws:backup:us-east-2:$account:backup-vault:Default"]


def test_ai_services_opt_out_at_the_root():
    assert policy_named(stack("lz-structure"), "acme-ai-opt-out")["Type"] == "AISERVICES_OPT_OUT_POLICY"


def test_no_ou_exceeds_the_scp_quota_in_any_variant():
    for overrides in VARIANTS.values():
        design = LandingZoneDesigner.default().design(answers(**overrides), CATALOG)
        assert ScpQuotaRule().problems(GuardrailPlan.for_design(design)) == []


def test_scp_quota_rule_reports_overloaded_ous():
    design = LandingZoneDesigner.default().design(answers(), CATALOG)
    plan = GuardrailPlan.for_design(design)
    prod = design.ou_named("PROD")
    for index in range(2):
        plan.attach_scp(f"extra-{index}", prod)
    assert ScpQuotaRule().problems(plan) == [
        "OU 'PROD' would have 6 SCPs; AWS Organizations allows 5 including FullAWSAccess."]


# ---- accounts ----

def account_products(edits: list[dict] | None = None, **overrides) -> dict:
    return resources(stack("lz-accounts", edits, **overrides), "AWS::ServiceCatalog::CloudFormationProvisionedProduct")


def provisioning(body: dict) -> dict:
    return {item["Key"]: item["Value"] for item in body["Properties"]["ProvisioningParameters"]}


def test_accounts_are_vended_by_account_factory_except_log_archive_and_audit():
    names = [provisioning(body)["AccountName"] for body in account_products().values()]
    assert "acme-audit" not in names and names[:2] == ["acme-security-tooling", "acme-network"]


def test_account_lands_in_its_ou():
    body = next(body for body in account_products().values() if provisioning(body)["AccountName"] == "acme-payments-prod")
    assert provisioning(body)["ManagedOrganizationalUnit"] == {
        "Fn::Sub": ["PROD (${OuId})", {"OuId": {"Fn::ImportValue": "acme-lz-OuProdId"}}]}


def test_accounts_in_control_tower_ous_use_the_parameter():
    body = next(body for body in account_products().values()
                if provisioning(body)["AccountName"] == "acme-payments-sandbox")
    assert provisioning(body)["ManagedOrganizationalUnit"] == {"Fn::Sub": "Sandbox (${SandboxOuId})"}


def test_accounts_are_vended_one_at_a_time():
    keys = list(account_products())
    template = stack("lz-accounts")
    assert template["Resources"][keys[1]]["DependsOn"] == [keys[0]]


def test_vended_accounts_are_retained_on_stack_deletion():
    assert {body["DeletionPolicy"] for body in account_products().values()} == {"Retain"}


def test_network_account_id_is_exported():
    assert stack("lz-accounts")["Outputs"]["NetworkAccountId"]["Export"]["Name"] == "acme-lz-NetworkAccountId"


# ---- network (deployed into the Network account, once per governed region) ----

def test_one_vpc_per_environment_with_planned_cidrs():
    template = stack("lz-network")
    assert template["Mappings"]["Cidrs"]["us-east-1"]["Prod"] == "10.64.0.0/16"


def test_environment_vpcs_take_their_cidr_for_the_region():
    assert properties(stack("lz-network"), "VpcProd")["CidrBlock"] == {
        "Fn::FindInMap": ["Cidrs", {"Ref": "AWS::Region"}, "Prod"]}


def test_environment_subnets_are_shared_with_their_ou_only():
    share = properties(stack("lz-network"), "ShareProd")
    assert share["Principals"] == [{"Ref": "OuProdArn"}] and share["AllowExternalPrincipals"] is False


def test_environment_vpc_has_an_org_security_group_for_its_own_range():
    group = properties(stack("lz-network"), "OrgSecurityGroupProd")
    assert group["SecurityGroupIngress"] == [{"IpProtocol": "-1", "CidrIp": {"Fn::GetAtt": ["VpcProd", "CidrBlock"]},
                                              "Description": "Anything inside the PROD environment"}]


def test_org_security_group_is_shared_with_the_environment_ou():
    arns = properties(stack("lz-network"), "ShareProd")["ResourceArns"]
    assert {"Fn::Sub": "arn:${AWS::Partition}:ec2:${AWS::Region}:${AWS::AccountId}:security-group/${OrgSecurityGroupProd}"} in arns


def test_each_environment_has_its_own_transit_gateway_route_table():
    tables = resources(stack("lz-network"), "AWS::EC2::TransitGatewayRouteTable")
    assert {"RouteTableSandbox", "RouteTableDev", "RouteTableProd", "RouteTableShared"} <= set(tables)


def propagations_into(template: dict, table: str) -> list[str]:
    return [body["Properties"]["TransitGatewayAttachmentId"]["Ref"]
            for body in resources(template, "AWS::EC2::TransitGatewayRouteTablePropagation").values()
            if body["Properties"]["TransitGatewayRouteTableId"] == {"Ref": table}]


def test_environment_route_table_learns_only_its_own_vpc_and_shared_services():
    assert propagations_into(stack("lz-network"), "RouteTableProd") == ["AttachmentProd", "AttachmentSharedServices"]


def test_shared_route_table_learns_every_environment_for_return_traffic():
    assert set(propagations_into(stack("lz-network"), "RouteTableShared")) >= {"AttachmentDev", "AttachmentProd"}


def test_sandbox_route_table_has_egress_only():
    template = stack("lz-network")
    routes = [body["Properties"] for body in resources(template, "AWS::EC2::TransitGatewayRoute").values()
              if body["Properties"]["TransitGatewayRouteTableId"] == {"Ref": "RouteTableSandbox"}]
    assert (propagations_into(template, "RouteTableSandbox"), [route["DestinationCidrBlock"] for route in routes]) == (
        ["AttachmentSandbox"], ["0.0.0.0/0"])


def test_firewall_drops_internal_traffic_by_default():
    rules = properties(stack("lz-network"), "FirewallRules")["RuleGroup"]["RulesSource"]["RulesString"]
    assert "drop ip $HOME_NET any -> $HOME_NET any" in rules


def test_declared_flows_become_single_port_firewall_rules():
    rules = properties(stack("lz-network", network={"flows": [FLOW]}), "FirewallRules")["RuleGroup"]["RulesSource"][
        "RulesString"]
    assert ('pass tcp [10.16.0.0/16,10.144.0.0/16] any -> [10.32.0.0/16,10.160.0.0/16] 5432 '
            '(msg:"dev to test: Data refresh"; sid:1000001; rev:1;)') in rules


def test_no_inspection_means_no_firewall():
    assert resources(stack("lz-network", network={"inspection": False}), "AWS::NetworkFirewall::Firewall") == {}


def test_local_egress_puts_nat_in_each_environment_vpc():
    template = stack("lz-network", network={"egress": "local"})
    assert ("NatProd" in template["Resources"], "VpcEgress" in template["Resources"]) == (True, False)


def test_without_a_hub_there_is_no_transit_gateway():
    assert resources(stack("lz-network", infrastructure=["shared_services"], network={"hub": False}),
                     "AWS::EC2::TransitGateway") == {}


def test_network_outputs_vpc_and_subnets_for_the_registry():
    outputs = stack("lz-network")["Outputs"]
    assert {"VpcProdId", "VpcProdPrivateSubnetIds", "VpcProdCidr", "VpcProdSecurityGroupId"} <= set(outputs)


# ---- bootstrap ----

def test_bootstrap_stack_set_auto_deploys_to_workload_ous():
    stack_set = next(iter(resources(stack("lz-bootstrap"), "AWS::CloudFormation::StackSet").values()))["Properties"]
    targets = stack_set["StackInstancesGroup"][0]["DeploymentTargets"]["OrganizationalUnitIds"]
    assert (stack_set["PermissionModel"], stack_set["AutoDeployment"]["Enabled"], targets[:2]) == (
        "SERVICE_MANAGED", True, [{"Ref": "SandboxOuId"}, {"Fn::ImportValue": "acme-lz-OuDevId"}])


def test_bootstrap_template_creates_the_github_oidc_provider():
    stack_set = next(iter(resources(stack("lz-bootstrap"), "AWS::CloudFormation::StackSet").values()))["Properties"]
    inner = yaml.safe_load(stack_set["TemplateBody"])
    assert inner["Resources"]["GitHubOidcProvider"]["Properties"]["Url"] == "https://token.actions.githubusercontent.com"


def test_bootstrap_inner_template_has_no_cfn_lint_findings():
    stack_set = next(iter(resources(stack("lz-bootstrap"), "AWS::CloudFormation::StackSet").values()))["Properties"]
    assert [str(match) for match in lint(stack_set["TemplateBody"], config=ManualArgs(regions=["us-east-1"]))] == []


# ---- the editor's changes ----

def test_root_level_custom_ou_gets_its_own_isolation_scp():
    assert policy_named(stack("lz-structure", EDITS), "acme-isolation-custom_data_lab")["TargetIds"] == [
        {"Ref": "OuCustomDataLab"}]


def test_root_level_custom_ou_gets_its_own_resource_perimeter():
    assert policy_named(stack("lz-structure", EDITS), "acme-resource-perimeter-custom_data_lab")["TargetIds"] == [
        {"Ref": "OuCustomDataLab"}]


def test_root_level_custom_ou_gets_the_workload_baseline():
    assert {"Ref": "OuCustomDataLab"} in policy_named(stack("lz-structure", EDITS), "acme-workload-baseline")["TargetIds"]


def test_root_level_custom_ou_gets_the_profile_controls():
    assert "AWS-GR_S3_BUCKET_PUBLIC_READ_PROHIBITED" in controls_on(stack("lz-structure", EDITS), "OuCustomDataLab")


def test_child_ous_inherit_instead_of_getting_their_own_guardrails():
    template = stack("lz-structure", EDITS)
    names = [body["Properties"]["Name"] for body in resources(template, "AWS::Organizations::Policy").values()]
    assert (controls_on(template, "OuCustomPayments"), [name for name in names if "payments" in name]) == ([], [])


def test_child_ou_is_created_under_its_environment():
    assert properties(stack("lz-structure", EDITS), "OuCustomPayments")["ParentId"] == {"Ref": "OuProd"}


def test_moved_account_lands_in_the_child_ou():
    body = next(body for body in account_products(EDITS).values()
                if provisioning(body)["AccountName"] == "acme-payments-prod")
    assert provisioning(body)["ManagedOrganizationalUnit"] == {
        "Fn::Sub": ["Payments (${OuId})", {"OuId": {"Fn::ImportValue": "acme-lz-OuCustomPaymentsId"}}]}


def test_disabled_accounts_are_not_vended():
    assert "acme-retail-prod" not in [provisioning(body)["AccountName"] for body in account_products(EDITS).values()]


def test_edited_design_stays_within_the_scp_quota():
    design = edited(EDITS)[0]
    assert ScpQuotaRule().problems(GuardrailPlan.for_design(design, CATALOG)) == []
