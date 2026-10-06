from app.providers.azure.expressions import ArmExpressions
from app.providers.azure.naming import resource_group, resource_group_id
from app.providers.azure.project.naming import VAULT_NAME
from app.synth.toolkit import WorkflowVariables

REGION_SUFFIXES = ("", "_SECONDARY")


class AzureEnvironmentVariables(WorkflowVariables):
    """GitHub environment variables: the only place subscription, tenant and identity ids appear. The contract
    vault's name lets the workflow recover it after a teardown (§22.11.6)."""

    def for_environment(self, context, environment: str) -> dict[str, str]:
        primary, *secondaries = context.topology.regions_for(environment)
        outputs = context.bootstrap_outputs[(environment, primary)]
        project = context.request.project_name
        variables = {"ENVIRONMENT_NAME": environment, "AZURE_SUBSCRIPTION_ID": context.accounts[environment],
                     "AZURE_CLIENT_ID": outputs.federation, "AZURE_TENANT_ID": outputs.directory,
                     "AZURE_RESOURCE_GROUP": resource_group(project, environment), "AZURE_PRIMARY_REGION": primary,
                     "CONTRACT_VAULT": ArmExpressions({}, {}, resource_group_id(
                         context.accounts[environment], project, environment)).evaluate(VAULT_NAME)}
        for secondary in secondaries:
            variables.update({"AZURE_SECONDARY_REGION": secondary,
                              "ACTIVATION_STATE_SECONDARY": context.topology.secondary_activation()})
        for region, suffix in zip([primary, *secondaries], REGION_SUFFIXES, strict=False):
            network = context.networks.get((environment, region))
            if network is not None:
                functions, *rest = network["subnet_refs"]
                variables.update({f"SUBNET_ID{suffix}": functions, f"ENDPOINT_SUBNET_ID{suffix}": (rest or [functions])[0]})
        return variables
