import json

from app.synth.toolkit import WorkflowVariables

CODE_BUCKET_PATTERN = "cloudinfra-artifacts-{project}-{region}"
REGION_SUFFIXES = ("", "_SECONDARY")


class GcpEnvironmentVariables(WorkflowVariables):
    """GitHub environment variables: the only place project ids, service accounts and regions appear."""

    def for_environment(self, context, environment: str) -> dict[str, str]:
        project = context.accounts[environment]
        primary, *secondaries = context.topology.regions_for(environment)
        outputs = context.bootstrap_outputs[(environment, primary)]
        variables = {"ENVIRONMENT_NAME": environment, "GCP_PROJECT_ID": project, "GCP_PRIMARY_REGION": primary,
                     "GCP_WORKLOAD_IDENTITY_PROVIDER": outputs.federation,
                     "GCP_DEPLOY_SERVICE_ACCOUNT": outputs.deployer_identity,
                     "IM_SERVICE_ACCOUNT": outputs.execution_identity,
                     "CODE_BUCKET": CODE_BUCKET_PATTERN.format(project=project, region=primary)}
        for secondary in secondaries:
            variables.update({"GCP_SECONDARY_REGION": secondary,
                              "ACTIVATION_STATE_SECONDARY": context.topology.secondary_activation(),
                              "CODE_BUCKET_SECONDARY": CODE_BUCKET_PATTERN.format(project=project, region=secondary)})
        for region, suffix in zip([primary, *secondaries], REGION_SUFFIXES, strict=False):
            variables.update(self._network(context, environment, region, suffix))
        return variables

    def _network(self, context, environment: str, region: str, suffix: str) -> dict[str, str]:
        network = context.networks.get((environment, region))
        if network is None:
            return {}
        return {f"NETWORK{suffix}": network["network_ref"], f"SUBNETWORK{suffix}": network["subnet_refs"][0],
                f"NETWORK_TAGS{suffix}": json.dumps(network["firewall_refs"], separators=(",", ":"))}
