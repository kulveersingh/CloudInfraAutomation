import json
from pathlib import Path

from app.adapters.ports import AwsPort, BootstrapOutputs, BootstrapRequest
from app.config import Settings

STATE_FILE = "bootstrap-stacks.json"


class LocalAws(AwsPort):
    """AWS stand-in for local development: records the bootstrap stacks that would be deployed."""

    def __init__(self, root):
        self._state_file = Path(root) / "aws" / STATE_FILE

    @classmethod
    def from_settings(cls, settings: Settings) -> "LocalAws":
        return cls(settings.local_state_dir)

    def stacks(self) -> list[dict]:
        if not self._state_file.exists():
            return []
        return json.loads(self._state_file.read_text())

    def ensure_bootstrap_stack(self, request: BootstrapRequest) -> BootstrapOutputs:
        outputs = BootstrapOutputs(
            deploy_role_arn=self._role_arn(request, "deploy"),
            cfn_execution_role_arn=self._role_arn(request, "cfn-exec"))
        self._save([*self._others(request), self._record(request, outputs)])
        return outputs

    def delete_bootstrap_stack(self, request: BootstrapRequest) -> None:
        self._save(self._others(request))

    def _role_arn(self, request: BootstrapRequest, role: str) -> str:
        return f"arn:aws:iam::{request.account_id}:role/cloudinfra/{request.project}-{role}"

    def _others(self, request: BootstrapRequest) -> list[dict]:
        key = (request.stack_name, request.account_id, request.region)
        return [stack for stack in self.stacks() if (stack["stack"], stack["account"], stack["region"]) != key]

    def _record(self, request: BootstrapRequest, outputs: BootstrapOutputs) -> dict:
        return {"stack": request.stack_name, "account": request.account_id, "region": request.region,
                "environment": request.environment, "trust_subject": request.trust_subject,
                "deploy_role_arn": outputs.deploy_role_arn,
                "cfn_execution_role_arn": outputs.cfn_execution_role_arn}

    def _save(self, stacks: list[dict]) -> None:
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        self._state_file.write_text(json.dumps(stacks, indent=2, sort_keys=True))
