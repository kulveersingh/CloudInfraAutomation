from dataclasses import dataclass, field

from app.landing_zone.cloudformation.references import OuReferences
from app.landing_zone.design import LandingZoneDesign, OrgCatalog, OuNode

SCP = "SERVICE_CONTROL_POLICY"
RCP = "RESOURCE_CONTROL_POLICY"
SCP_QUOTA = 5
POLICY_VERSION = "2012-10-17"
CONTROL_TOWER_EXECUTION = "arn:aws:iam::*:role/AWSControlTowerExecution"
BREAK_GLASS = "arn:aws:iam::*:role/BreakGlass"
RELEASE_EXECUTOR = "arn:aws:iam::*:role/PlatformReleaseExecutor"
NETWORK_ADMIN = "arn:aws:iam::*:role/NetworkAdmin"
BASELINE_KINDS = frozenset({"environment", "parent", "compliance", "policy_staging", "exceptions", "business_users",
                            "automations", "custom_domain"})
GLOBAL_SERVICES = ["iam:*", "organizations:*", "sts:*", "support:*", "cloudfront:*", "route53:*", "route53domains:*",
                   "waf:*", "budgets:*", "ce:*", "cur:*", "health:*", "trustedadvisor:*", "account:*",
                   "controltower:*", "sso:*", "globalaccelerator:*", "shield:*", "pricing:*", "s3:ListAllMyBuckets",
                   "s3:GetAccountPublicAccessBlock", "s3:PutAccountPublicAccessBlock", "ec2:DescribeRegions"]

BASELINE_CONTROLS = ["AWS-GR_RESTRICT_ROOT_USER", "AWS-GR_RESTRICT_ROOT_USER_ACCESS_KEYS"]
RECOMMENDED_CONTROLS = ["AWS-GR_ROOT_ACCOUNT_MFA_ENABLED", "AWS-GR_MFA_ENABLED_FOR_IAM_CONSOLE_ACCESS",
                        "AWS-GR_S3_BUCKET_PUBLIC_READ_PROHIBITED", "AWS-GR_S3_BUCKET_PUBLIC_WRITE_PROHIBITED",
                        "AWS-GR_RDS_INSTANCE_PUBLIC_ACCESS_CHECK", "AWS-GR_RDS_SNAPSHOTS_PUBLIC_PROHIBITED",
                        "AWS-GR_RDS_STORAGE_ENCRYPTED", "AWS-GR_ENCRYPTED_VOLUMES"]
PRODUCTION_CONTROLS = ["AWS-GR_RESTRICTED_SSH", "AWS-GR_RESTRICTED_COMMON_PORTS"]
REGULATED_CONTROLS = ["AWS-GR_EBS_OPTIMIZED_INSTANCE", "AWS-GR_EC2_VOLUME_INUSE_CHECK"]


@dataclass
class PolicySpec:
    name: str
    type: str
    content: dict
    targets: list[OuNode | None] = field(default_factory=list)  # None is the organization root


def _statement(sid: str, actions, condition: dict | None = None, **extra) -> dict:
    statement = {"Sid": sid, "Effect": "Deny", "Action": actions, "Resource": "*", **extra}
    return {**statement, "Condition": condition} if condition else statement


def _document(*statements: dict) -> dict:
    return {"Version": POLICY_VERSION, "Statement": list(statements)}


def _exempt(*principals: str) -> dict:
    return {"ArnNotLike": {"aws:PrincipalARN": list(principals)}}


class ControlCatalog:
    """Control Tower controls per OU for the chosen profile. Identifiers are checked against ListControls at plan time."""

    def controls_for(self, ou: OuNode, profile: str) -> list[str]:
        if ou.kind in {"security", "suspended", "parent", "compliance", "custom"}:
            return []
        if profile == "baseline":
            return list(BASELINE_CONTROLS)
        production = ou.tier == "prod" or ou.kind in {"infrastructure", "policy_staging"} or profile == "regulated"
        return [*BASELINE_CONTROLS, *RECOMMENDED_CONTROLS, *(PRODUCTION_CONTROLS if production else []),
                *(REGULATED_CONTROLS if profile == "regulated" else [])]


class GuardrailPlan:
    """Which organization policies and Control Tower controls attach to which OU."""

    def __init__(self, design: LandingZoneDesign, policies: list[PolicySpec], controls: dict[str, list[str]]):
        self.design = design
        self.policies = policies
        self.controls = controls

    @classmethod
    def for_design(cls, design: LandingZoneDesign, catalog: OrgCatalog | None = None) -> "GuardrailPlan":
        builder = PolicyBuilder(design, OuReferences(design), catalog or OrgCatalog(portfolios=[], products=[]))
        controls = {ou.key: ControlCatalog().controls_for(ou, design.answers.controls_profile) for ou in design.walk()}
        return cls(design, builder.policies(), {key: value for key, value in controls.items() if value})

    def attach_scp(self, name: str, ou: OuNode) -> None:
        self.policies.append(PolicySpec(name=name, type=SCP, content=_document(_statement(name, "*")), targets=[ou]))

    def scp_count(self, ou: OuNode) -> int:
        return sum(1 for policy in self.policies if policy.type == SCP and ou in policy.targets)


class ScpQuotaRule:
    """AWS Organizations allows five SCPs per OU, and FullAWSAccess is always one of them."""

    def problems(self, plan: GuardrailPlan) -> list[str]:
        counts = [(ou, plan.scp_count(ou) + 1) for ou in plan.design.walk()]
        return [f"OU '{ou.name}' would have {count} SCPs; AWS Organizations allows {SCP_QUOTA} including FullAWSAccess."
                for ou, count in counts if count > SCP_QUOTA]


class PolicyBuilder:
    def __init__(self, design: LandingZoneDesign, references: OuReferences, catalog: OrgCatalog):
        self._design = design
        self._answers = design.answers
        self._refs = references
        self._catalog = catalog
        self._prefix = design.answers.organization_name

    def policies(self) -> list[PolicySpec]:
        isolated = self._design.isolated_ous()
        policies = [self._baseline(), *map(self._isolation, isolated), *map(self._perimeter, isolated),
                    self._production_protection(), self._sandbox_limits(), self._infrastructure(), self._security(),
                    *self._compliance(), *self._suspended(), self._tag_policy(), self._backup(), self._ai_opt_out()]
        return [policy for policy in policies if policy.targets]

    def _of_kind(self, *kinds: str) -> list[OuNode]:
        return [ou for ou in self._design.walk() if ou.kind in kinds]

    def _baseline_targets(self) -> list[OuNode]:
        covered: list[OuNode] = []
        for ou in self._design.walk():
            ancestors = self._refs.ancestors(ou)[:-1]
            if ou.kind in BASELINE_KINDS and not any(ancestor in covered for ancestor in ancestors):
                covered.append(ou)
        return covered

    def _baseline(self) -> PolicySpec:
        content = _document(
            _statement("DenyLeavingTheOrganization", "organizations:LeaveOrganization"),
            _statement("DenySecurityServiceTampering",
                       ["guardduty:DeleteDetector", "guardduty:DisassociateFromMasterAccount",
                        "securityhub:DisableSecurityHub", "config:DeleteConfigurationRecorder",
                        "config:StopConfigurationRecorder", "cloudtrail:StopLogging", "cloudtrail:DeleteTrail",
                        "access-analyzer:DeleteAnalyzer"], _exempt(CONTROL_TOWER_EXECUTION)),
            {"Sid": "DenyUngovernedRegions", "Effect": "Deny", "NotAction": GLOBAL_SERVICES, "Resource": "*",
             "Condition": {"StringNotEquals": {"aws:RequestedRegion": self._answers.governed_regions},
                           **_exempt(CONTROL_TOWER_EXECUTION)}},
            _statement("DenyRootUser", "*", {"StringLike": {"aws:PrincipalARN": "arn:aws:iam::*:root"}}))
        return PolicySpec(f"{self._prefix}-workload-baseline", SCP, content, self._baseline_targets())

    def _isolation(self, ou: OuNode) -> PolicySpec:
        content = _document(
            _statement("DenyRoleAssumptionOutsideEnvironment", "sts:AssumeRole",
                       {"ForAllValues:StringNotLike": {"aws:ResourceOrgPaths": self._refs.path(ou)},
                        **_exempt(CONTROL_TOWER_EXECUTION, BREAK_GLASS)}),
            _statement("DenyExternalResourceShares", ["ram:CreateResourceShare", "ram:AssociateResourceShare"],
                       {"Bool": {"ram:RequestedAllowsExternalPrincipals": "true"}}))
        return PolicySpec(f"{self._prefix}-isolation-{ou.key}", SCP, content, [ou])

    def _perimeter(self, ou: OuNode) -> PolicySpec:
        allowed = [self._refs.path(item) for item in (ou, *self._of_kind("security", "infrastructure"))]
        statement = _statement("EnforceEnvironmentPerimeter",
                               ["s3:*", "sqs:*", "kms:*", "secretsmanager:*", "sts:AssumeRole"],
                               {"ForAllValues:StringNotLike": {"aws:PrincipalOrgPaths": allowed},
                                "BoolIfExists": {"aws:PrincipalIsAWSService": "false"}}, Principal="*")
        return PolicySpec(f"{self._prefix}-resource-perimeter-{ou.key}", RCP, _document(statement), [ou])

    def _production_protection(self) -> PolicySpec:
        content = _document(_statement(
            "DenyDeletingProductionData",
            ["cloudformation:DeleteStack", "dynamodb:DeleteTable", "rds:DeleteDBCluster", "rds:DeleteDBInstance",
             "s3:DeleteBucket", "backup:DeleteRecoveryPoint"],
            _exempt(RELEASE_EXECUTOR, BREAK_GLASS, CONTROL_TOWER_EXECUTION)))
        targets = [ou for ou in self._design.environment_ous() if ou.tier == "prod"]
        return PolicySpec(f"{self._prefix}-production-protection", SCP, content, targets)

    def _sandbox_limits(self) -> PolicySpec:
        content = _document(
            _statement("DenyLargeInstances", "ec2:RunInstances",
                       {"ForAnyValue:StringNotLike": {"ec2:InstanceType": ["t3.*", "t4g.*"]}}),
            _statement("DenyCostlyServices", ["redshift:CreateCluster", "sagemaker:CreateEndpoint", "es:CreateDomain",
                                              "ec2:PurchaseReservedInstancesOffering", "savingsplans:CreateSavingsPlan"]))
        targets = [ou for ou in self._design.environment_ous() if ou.tier == "sandbox"]
        return PolicySpec(f"{self._prefix}-sandbox-limits", SCP, content, targets)

    def _infrastructure(self) -> PolicySpec:
        content = _document(_statement(
            "OnlyNetworkAdminsChangeTheHub",
            ["ec2:CreateTransitGateway*", "ec2:DeleteTransitGateway*", "ec2:ModifyTransitGateway*",
             "network-firewall:Delete*", "network-firewall:Update*", "ram:DisassociateResourceShare"],
            _exempt(NETWORK_ADMIN, CONTROL_TOWER_EXECUTION, BREAK_GLASS)))
        return PolicySpec(f"{self._prefix}-network-admin-only", SCP, content, self._of_kind("infrastructure"))

    def _security(self) -> PolicySpec:
        content = _document(_statement("DenyLongLivedCredentials", ["iam:CreateUser", "iam:CreateAccessKey"],
                                       _exempt(CONTROL_TOWER_EXECUTION)))
        return PolicySpec(f"{self._prefix}-security-protection", SCP, content, self._of_kind("security"))

    def _compliance(self) -> list[PolicySpec]:
        content = _document(_statement("KeepComplianceStandardsOn",
                                       ["securityhub:BatchDisableStandards", "securityhub:DisableSecurityHub"],
                                       _exempt(CONTROL_TOWER_EXECUTION)))
        return [PolicySpec(f"{self._prefix}-compliance-{ou.key}", SCP, content, [ou])
                for ou in self._of_kind("compliance")]

    def _suspended(self) -> list[PolicySpec]:
        content = _document(_statement("DenyEverythingButBreakGlass", "*",
                                       _exempt(BREAK_GLASS, CONTROL_TOWER_EXECUTION)))
        return [PolicySpec(f"{self._prefix}-suspended-deny-all", SCP, content, self._of_kind("suspended"))]

    def _tag_policy(self) -> PolicySpec:
        def tag(key: str, values: list[str]) -> dict:
            return {"tag_key": {"@@assign": key}, "tag_value": {"@@assign": values}}

        tags = {"org:portfolio": tag("org:portfolio", self._catalog.portfolios),
                "org:product": tag("org:product", self._catalog.products)}
        return PolicySpec(f"{self._prefix}-tag-policy", "TAG_POLICY", {"tags": tags}, [None])

    def _backup(self) -> PolicySpec:
        home = self._answers.home_region
        copy_region = next(region for region in self._answers.governed_regions if region != home)
        vault = f"arn:aws:backup:{copy_region}:$account:backup-vault:Default"
        rule = {"schedule_expression": {"@@assign": "cron(0 5 ? * * *)"},
                "target_backup_vault_name": {"@@assign": "Default"},
                "lifecycle": {"delete_after_days": {"@@assign": "35"}},
                "copy_actions": {vault: {"target_backup_vault_arn": {"@@assign": vault},
                                         "lifecycle": {"delete_after_days": {"@@assign": "35"}}}}}
        selection = {"iam_role_arn": {"@@assign": "arn:aws:iam::$account:role/service-role/AWSBackupDefaultServiceRole"},
                     "tag_key": {"@@assign": "org:backup"}, "tag_value": {"@@assign": ["daily"]}}
        content = {"plans": {"daily": {"regions": {"@@assign": [home]}, "rules": {"daily": rule},
                                       "selections": {"tags": {"daily": selection}}}}}
        targets = [ou for ou in self._design.environment_ous() if ou.tier == "prod"]
        return PolicySpec(f"{self._prefix}-backup-production", "BACKUP_POLICY", content, targets)

    def _ai_opt_out(self) -> PolicySpec:
        content = {"services": {"default": {"opt_out_policy": {"@@assign": "optOut"}}}}
        return PolicySpec(f"{self._prefix}-ai-opt-out", "AISERVICES_OPT_OUT_POLICY", content, [None])
