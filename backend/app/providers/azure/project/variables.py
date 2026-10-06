from app.synth.toolkit import WorkflowVariables

REGION_SUFFIXES = ("", "_SECONDARY")


class AzureEnvironmentVariables(WorkflowVariables):
    """GitHub environment variables: the only place subscription, tenant and identity ids appear."""

    def for_environment(self, context, environment: str) -> dict[str, str]:
        primary, *secondaries = context.topology.regions_for(environment)
        outputs = context.bootstrap_outputs[(environment, primary)]
        variables = {"ENVIRONMENT_NAME": environment, "AZURE_SUBSCRIPTION_ID": context.accounts[environment],
                     "AZURE_CLIENT_ID": outputs.federation, "AZURE_TENANT_ID": outputs.directory,
                     "AZURE_RESOURCE_GROUP": f"rg-{context.request.project_name}-{environment}",
                     "AZURE_PRIMARY_REGION": primary}
        for secondary in secondaries:
            variables.update({"AZURE_SECONDARY_REGION": secondary,
                              "ACTIVATION_STATE_SECONDARY": context.topology.secondary_activation()})
        for region, suffix in zip([primary, *secondaries], REGION_SUFFIXES, strict=False):
            network = context.networks.get((environment, region))
            if network is not None:
                functions, *rest = network["subnet_refs"]
                variables.update({f"SUBNET_ID{suffix}": functions, f"ENDPOINT_SUBNET_ID{suffix}": (rest or [functions])[0]})
        return variables
