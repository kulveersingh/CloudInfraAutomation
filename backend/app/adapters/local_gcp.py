from app.adapters.local_cloud import LocalCloud
from app.adapters.ports import BootstrapOutputs, BootstrapRequest

WORKLOAD_IDENTITY_PROVIDER = "projects/{project}/locations/global/workloadIdentityPools/cloudinfra-github/providers/github"


class LocalGcp(LocalCloud):
    """Google Cloud stand-in: Workload Identity Federation for GitHub, a deploy service account and the
    Infrastructure Manager service account in the environment's project (§22.9.1)."""

    provider = "gcp"

    def _outputs(self, request: BootstrapRequest) -> BootstrapOutputs:
        return BootstrapOutputs(deployer_identity=self._service_account(request, "deploy"),
                                execution_identity=self._service_account(request, "im"),
                                federation=WORKLOAD_IDENTITY_PROVIDER.format(project=request.account_id))

    def _service_account(self, request: BootstrapRequest, role: str) -> str:
        return f"cloudinfra-{request.project}-{role}@{request.account_id}.iam.gserviceaccount.com"
