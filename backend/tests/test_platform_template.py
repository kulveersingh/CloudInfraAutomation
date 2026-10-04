"""The CloudFormation template that deploys the platform itself on AWS (ECS Fargate + Aurora PostgreSQL)."""

from pathlib import Path

import pytest
import yaml

from app.synth.lint import CfnLintRunner, TemplateLinter, WildcardActionRule, WildcardResourceRule

TEMPLATE_PATH = Path(__file__).resolve().parents[2] / "infra" / "platform" / "platform.yaml"


@pytest.fixture(scope="module")
def template_text() -> str:
    return TEMPLATE_PATH.read_text()


@pytest.fixture(scope="module")
def template(template_text) -> dict:
    return yaml.safe_load(template_text)


def resources_of(template: dict, type_name: str) -> dict:
    return {name: body for name, body in template["Resources"].items() if body["Type"] == type_name}


def single(template: dict, type_name: str) -> dict:
    (body,) = resources_of(template, type_name).values()
    return body


def test_template_passes_cfn_lint(template_text):
    assert CfnLintRunner().errors(template_text) == []


def test_template_has_no_cfn_lint_warnings(template_text):
    from cfnlint.api import ManualArgs, lint

    assert [str(match) for match in lint(template_text, config=ManualArgs(regions=["us-east-1"]))] == []


def test_database_is_aurora_postgresql(template):
    assert single(template, "AWS::RDS::DBCluster")["Properties"]["Engine"] == "aurora-postgresql"


def test_database_is_protected(template):
    cluster = single(template, "AWS::RDS::DBCluster")
    properties = cluster["Properties"]
    assert (properties["StorageEncrypted"], properties["DeletionProtection"], properties["ManageMasterUserPassword"],
            cluster["DeletionPolicy"], cluster["UpdateReplacePolicy"]) == (True, True, True, "Snapshot", "Snapshot")


def test_database_scales_serverless(template):
    assert "ServerlessV2ScalingConfiguration" in single(template, "AWS::RDS::DBCluster")["Properties"]


def test_database_accepts_only_application_traffic(template):
    ingress = template["Resources"]["DatabaseSecurityGroup"]["Properties"]["SecurityGroupIngress"]
    assert ingress == [{"IpProtocol": "tcp", "FromPort": 5432, "ToPort": 5432,
                        "SourceSecurityGroupId": {"Ref": "ApplicationSecurityGroup"},
                        "Description": "PostgreSQL from platform tasks only"}]


def test_three_fargate_services(template):
    services = resources_of(template, "AWS::ECS::Service")
    assert sorted(services) == ["ApiService", "UiService", "WorkerService"]


def test_services_run_on_fargate_in_private_subnets(template):
    services = resources_of(template, "AWS::ECS::Service").values()
    assert all(service["Properties"]["LaunchType"] == "FARGATE" and service["Properties"]["NetworkConfiguration"][
        "AwsvpcConfiguration"]["AssignPublicIp"] == "DISABLED" for service in services)


def test_services_roll_back_failed_deployments(template):
    services = resources_of(template, "AWS::ECS::Service").values()
    assert all(service["Properties"]["DeploymentConfiguration"]["DeploymentCircuitBreaker"] == {
        "Enable": True, "Rollback": True} for service in services)


def test_worker_runs_the_provisioning_worker(template):
    container = template["Resources"]["WorkerTaskDefinition"]["Properties"]["ContainerDefinitions"][0]
    assert container["Command"] == ["python", "-m", "app.provisioning.worker"]


def test_database_password_comes_from_managed_secret(template):
    container = template["Resources"]["ApiTaskDefinition"]["Properties"]["ContainerDefinitions"][0]
    secret = next(item for item in container["Secrets"] if item["Name"] == "DATABASE_PASSWORD")
    assert secret["ValueFrom"] == {"Fn::Sub": "${DatabaseCluster.MasterUserSecret.SecretArn}:password::"}


def test_load_balancer_routes_api_paths(template):
    rule = single(template, "AWS::ElasticLoadBalancingV2::ListenerRule")["Properties"]
    assert (rule["Conditions"][0]["PathPatternConfig"]["Values"], rule["Actions"][0]["TargetGroupArn"]) == (
        ["/v1/*", "/healthz"], {"Ref": "ApiTargetGroup"})


def test_https_listener_uses_modern_tls(template):
    listeners = resources_of(template, "AWS::ElasticLoadBalancingV2::Listener").values()
    https = next(listener for listener in listeners if listener["Properties"]["Protocol"] == "HTTPS")
    assert https["Properties"]["SslPolicy"].startswith("ELBSecurityPolicy-TLS13")


def test_platform_roles_have_no_wildcards(template):
    assert TemplateLinter([WildcardActionRule(), WildcardResourceRule()]).lint(template) == []


def test_logs_are_retained(template):
    groups = resources_of(template, "AWS::Logs::LogGroup").values()
    assert all(group["Properties"]["RetentionInDays"] >= 30 for group in groups)
