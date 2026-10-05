import json
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from pathlib import Path
from typing import ClassVar

from app.adapters.local_backup import LocalBackup
from app.adapters.ports import BootstrapOutputs, BootstrapRequest, ProviderPort
from app.config import Settings

STATE_FILE = "bootstrap-stacks.json"
OPERATIONS_FILE = "stack-operations.json"


class LocalCloud(ProviderPort, ABC):
    """A cloud stand-in for local development: records bootstrap, deletions and imports under `<root>/<provider>`."""

    provider: ClassVar[str]

    def __init__(self, root):
        self._root = root
        self._state_file = Path(root) / self.provider / STATE_FILE
        self._operations_file = Path(root) / self.provider / OPERATIONS_FILE

    @classmethod
    def from_settings(cls, settings: Settings) -> "LocalCloud":
        return cls(settings.local_state_dir)

    def stacks(self) -> list[dict]:
        if not self._state_file.exists():
            return []
        return json.loads(self._state_file.read_text())

    def ensure_bootstrap_stack(self, request: BootstrapRequest) -> BootstrapOutputs:
        outputs = self._outputs(request)
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
        return LocalBackup(self._root, backup_account_id, provider=self.provider)

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

    @abstractmethod
    def _outputs(self, request: BootstrapRequest) -> BootstrapOutputs:
        """The identities the bootstrap creates: who deploys, and who applies the IaC document."""

    def _others(self, request: BootstrapRequest) -> list[dict]:
        key = (request.stack_name, request.account_id, request.region)
        return [stack for stack in self.stacks() if (stack["stack"], stack["account"], stack["region"]) != key]

    def _record(self, request: BootstrapRequest, outputs: BootstrapOutputs) -> dict:
        return {"stack": request.stack_name, "account": request.account_id, "region": request.region,
                "environment": request.environment, "trust_subject": request.trust_subject,
                "deployer_identity": outputs.deployer_identity,
                "execution_identity": outputs.execution_identity}

    def _save(self, stacks: list[dict]) -> None:
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        self._state_file.write_text(json.dumps(stacks, indent=2, sort_keys=True))
