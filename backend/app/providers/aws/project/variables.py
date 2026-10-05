from app.synth.toolkit import WorkflowVariables

ARTIFACT_BUCKET_PATTERN = "cloudinfra-artifacts-{region}"
REGION_SUFFIXES = ("", "_SECONDARY")


class AwsEnvironmentVariables(WorkflowVariables):
    """GitHub environment variables: the only place account numbers, roles and regions appear."""

    def for_environment(self, context, environment: str) -> dict[str, str]:
        primary, *secondaries = context.topology.regions_for(environment)
        outputs = context.bootstrap_outputs[(environment, primary)]
        variables = {"ENVIRONMENT_NAME": environment, "AWS_ACCOUNT_ID": context.accounts[environment],
                     "AWS_PRIMARY_REGION": primary, "AWS_ROLE_ARN": outputs.deployer_identity,
                     "CFN_EXEC_ROLE_ARN": outputs.execution_identity,
                     "ARTIFACT_BUCKET": ARTIFACT_BUCKET_PATTERN.format(region=primary)}
        for secondary in secondaries:
            variables.update(self._secondary(context, secondary))
        for region, suffix in zip([primary, *secondaries], REGION_SUFFIXES, strict=False):
            variables.update(self._network(context, environment, region, suffix))
        return variables

    def _network(self, context, environment: str, region: str, suffix: str) -> dict[str, str]:
        network = context.networks.get((environment, region))
        if network is None:
            return {}
        return {f"VPC_ID{suffix}": network["vpc_id"],
                f"PRIVATE_SUBNET_IDS{suffix}": ",".join(network["private_subnet_ids"]),
                f"ORG_SECURITY_GROUP_IDS{suffix}": ",".join(network["security_group_ids"]),
                f"ORG_PRIVATE_CIDR{suffix}": network["cidr"]}

    def _secondary(self, context, region: str) -> dict[str, str]:
        return {"AWS_SECONDARY_REGION": region,
                "ACTIVATION_STATE_SECONDARY": context.topology.secondary_activation(),
                "ARTIFACT_BUCKET_SECONDARY": ARTIFACT_BUCKET_PATTERN.format(region=region)}
