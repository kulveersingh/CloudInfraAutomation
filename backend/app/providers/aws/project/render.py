import json

import yaml

from app.synth.render import FileRenderer, InfraJsonRenderer, ReadmeRenderer, RepositoryBundle
from app.synth.request import ProjectRequest

SECONDARY_ACTIVATION = {"dr": "standby", "ha": "active"}
TEMPLATE_FILE = "template.yaml"


class NoAliasDumper(yaml.SafeDumper):
    """CloudFormation rejects YAML anchors and aliases, so repeated values are always written out in full."""

    def ignore_aliases(self, data):
        return True


class TemplateYamlRenderer(FileRenderer):
    def render(self, request, template):
        return {TEMPLATE_FILE: yaml.dump(template, Dumper=NoAliasDumper, sort_keys=False, width=120)}


class EnvironmentConfigRenderer(FileRenderer):
    def render(self, request, template):
        return {f"config/{environment}.json": self._config(request, environment)
                for environment in request.environments}

    def _config(self, request: ProjectRequest, environment: str) -> str:
        parameters = {"ProjectName": request.project_name, "EnvironmentName": environment,
                      "ResilienceMode": request.resilience.mode}
        return json.dumps({"Parameters": parameters}, indent=2) + "\n"


class DeployWorkflowRenderer(FileRenderer):
    """A workflow identical in every repo apart from region steps; all values come from GitHub variables."""

    HEADER = """name: deploy
on:
  push:
    branches: [main]
  workflow_dispatch:
    inputs:
      environment:
        description: Environment to deploy
        required: true
        default: dev
permissions:
  id-token: write
  contents: read
concurrency:
  group: deploy-${{ inputs.environment || 'dev' }}
  cancel-in-progress: false
jobs:
  deploy:
    runs-on: ubuntu-latest
    environment: ${{ inputs.environment || 'dev' }}
    steps:
      - uses: actions/checkout@v4
      - name: Lint template
        run: pip install cfn-lint && cfn-lint template.yaml
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ vars.AWS_ROLE_ARN }}
          aws-region: ${{ vars.AWS_PRIMARY_REGION }}
"""
    DEPLOY_STEP = """      - name: Deploy {label} region
        run: >
          aws cloudformation deploy --region "{region}"
          --stack-name "${{{{ vars.PROJECT_NAME }}}}" --template-file template.yaml
          --role-arn "${{{{ vars.CFN_EXEC_ROLE_ARN }}}}" --capabilities CAPABILITY_IAM --no-fail-on-empty-changeset
          --parameter-overrides ProjectName="${{{{ vars.PROJECT_NAME }}}}"
          EnvironmentName="${{{{ vars.ENVIRONMENT_NAME }}}}" ResilienceMode="${{{{ vars.RESILIENCE_MODE }}}}"
          RegionRole={role} ActivationState={activation}{overrides}
"""
    NETWORK_OVERRIDES = (' VpcId="${{{{ vars.VPC_ID{suffix} }}}}" PrivateSubnetIds="${{{{ vars.PRIVATE_SUBNET_IDS{suffix} }}}}"'
                         ' OrgSecurityGroupIds="${{{{ vars.ORG_SECURITY_GROUP_IDS{suffix} }}}}"'
                         ' OrgPrivateCidr="${{{{ vars.ORG_PRIVATE_CIDR{suffix} }}}}"')
    CODE_OVERRIDES = (' CodeS3Bucket="${{ vars.ARTIFACT_BUCKET }}"'
                      ' CodeS3Key="bootstrap/${{ vars.PROJECT_NAME }}.zip"')

    def render(self, request, template):
        parameters = template.get("Parameters", {})
        code = self.CODE_OVERRIDES if "CodeS3Bucket" in parameters else ""
        networked = "VpcId" in parameters
        steps = [self._step("primary", "${{ vars.AWS_PRIMARY_REGION }}", "primary", "active",
                            code + self._network(networked, ""))]
        steps += [self._step("secondary", "${{ vars.AWS_SECONDARY_REGION }}", "secondary", activation,
                             code + self._network(networked, "_SECONDARY"))
                  for activation in self._secondary_activations(request)]
        return {".github/workflows/deploy.yml": self.HEADER + "".join(steps)}

    def _secondary_activations(self, request: ProjectRequest) -> list[str]:
        activation = SECONDARY_ACTIVATION.get(request.resilience.mode)
        return [activation] if activation else []

    def _network(self, networked: bool, suffix: str) -> str:
        return self.NETWORK_OVERRIDES.format(suffix=suffix) if networked else ""

    def _step(self, label: str, region: str, role: str, activation: str, overrides: str) -> str:
        return self.DEPLOY_STEP.format(label=label, region=region, role=role, activation=activation,
                                       overrides=overrides)


def aws_bundle() -> RepositoryBundle:
    return RepositoryBundle([TemplateYamlRenderer(), InfraJsonRenderer(), EnvironmentConfigRenderer(),
                             DeployWorkflowRenderer(), ReadmeRenderer(TEMPLATE_FILE)])
