from app.adapters.local_cloud import LocalCloud
from app.adapters.ports import BootstrapOutputs, BootstrapRequest


class LocalAws(LocalCloud):
    """AWS stand-in: the bootstrap stack's deploy role and CloudFormation execution role."""

    provider = "aws"

    def _outputs(self, request: BootstrapRequest) -> BootstrapOutputs:
        return BootstrapOutputs(deployer_identity=self._role_arn(request, "deploy"),
                                execution_identity=self._role_arn(request, "cfn-exec"))

    def _role_arn(self, request: BootstrapRequest, role: str) -> str:
        return f"arn:aws:iam::{request.account_id}:role/cloudinfra/{request.project}-{role}"
