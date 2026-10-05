from app.adapters.local_cloud import LocalCloud
from app.adapters.ports import BootstrapOutputs, BootstrapRequest


class LocalGcp(LocalCloud):
    """Google Cloud stand-in: Workload Identity Federation for GitHub, a deploy service account and the
    Infrastructure Manager service account in the environment's project (§22.9.1)."""

    provider = "gcp"

    def _outputs(self, request: BootstrapRequest) -> BootstrapOutputs:
        return BootstrapOutputs(deployer_identity=self._service_account(request, "deploy"),
                                execution_identity=self._service_account(request, "im"))

    def _service_account(self, request: BootstrapRequest, role: str) -> str:
        return f"cloudinfra-{request.project}-{role}@{request.account_id}.iam.gserviceaccount.com"
