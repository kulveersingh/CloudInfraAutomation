import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from app.config import Settings

HISTORY_FILE = "release-executions.json"


@dataclass(frozen=True)
class ExecutionResult:
    succeeded: bool
    detail: str


class ReleaseExecutor(ABC):
    """Applies an approved release (executes its reviewed change set). The only writer to STAGE/PROD."""

    @abstractmethod
    def execute(self, release) -> ExecutionResult:
        ...


class LocalReleaseExecutor(ReleaseExecutor):
    """Local stand-in: records the change set it would execute and reports success."""

    def __init__(self, root):
        self._history_file = Path(root) / "aws" / HISTORY_FILE

    @classmethod
    def from_settings(cls, settings: Settings) -> "LocalReleaseExecutor":
        return cls(settings.local_state_dir)

    def execute(self, release) -> ExecutionResult:
        change_set = f"cs-{release.commit_sha}"
        self._record({"release_id": str(release.id), "project": release.project_name,
                      "environment": release.environment_id, "change_set": change_set})
        return ExecutionResult(True, f"Release executor applied change set {change_set} in {release.environment_id}.")

    def history(self) -> list[dict]:
        if not self._history_file.exists():
            return []
        return json.loads(self._history_file.read_text())

    def _record(self, entry: dict) -> None:
        self._history_file.parent.mkdir(parents=True, exist_ok=True)
        self._history_file.write_text(json.dumps([*self.history(), entry], indent=2))
