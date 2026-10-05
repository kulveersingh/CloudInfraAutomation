import json
from datetime import UTC, datetime
from pathlib import Path

from app.adapters.local_backup import LocalBackup
from app.adapters.ports import AwsPort, BootstrapOutputs, BootstrapRequest
from app.config import Settings

STATE_FILE = "bootstrap-stacks.json"
OPERATIONS_FILE = "stack-operations.json"


class LocalAws(AwsPort):
    """AWS stand-in for local development: records the bootstrap stacks that would be deployed."""

    def __init__(self, root):
        self._root = root
        self._state_file = Path(root) / "aws" / STATE_FILE
        self._operations_file = Path(root) / "aws" / OPERATIONS_FILE

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

    def allow_stack_deletion(self, account_id: str, region: str, stack_name: str) -> None:
        self._operate("allow_stack_deletion", account_id, region, stack_name)

    def delete_stack(self, account_id: str, region: str, stack_name: str) -> None:
        self._operate("delete_stack", account_id, region, stack_name)

    def delete_data_store(self, account_id: str, region: str, resource_type: str, physical_name: str) -> None:
        self._operate("delete_data_store", account_id, region, f"{resource_type} {physical_name}")

    def import_stack(self, account_id: str, region: str, stack_name: str, logical_ids: list[str]) -> None:
        self._operate("import_stack", account_id, region, f"{stack_name} {','.join(logical_ids)}")

    def backup(self, backup_account_id: str) -> LocalBackup:
        return LocalBackup(self._root, backup_account_id)

    def operations(self) -> list[dict]:
        """The stack and data-store operations, in order, each with when it happened."""
        if not self._operations_file.exists():
            return []
        return json.loads(self._operations_file.read_text())

    def _operate(self, operation: str, account_id: str, region: str, target: str) -> None:
        entry = {"operation": operation, "account": account_id, "region": region, "target": target,
                 "at": datetime.now(UTC).isoformat()}
        self._operations_file.parent.mkdir(parents=True, exist_ok=True)
        self._operations_file.write_text(json.dumps([*self.operations(), entry], indent=2))

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
