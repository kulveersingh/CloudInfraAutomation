import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from app.adapters.ports import GitHubPort, RepositoryConflictError
from app.config import Settings

BRANCH = "main"
MARKER_FILE = "cloudinfra-marker"
SETTINGS_FILE = "cloudinfra-settings.json"
FILE_MODE = "100644"
COMMITTER = {"GIT_AUTHOR_NAME": "CloudInfra Platform", "GIT_AUTHOR_EMAIL": "platform@cloudinfra.local",
             "GIT_COMMITTER_NAME": "CloudInfra Platform", "GIT_COMMITTER_EMAIL": "platform@cloudinfra.local"}


class LocalGitHub(GitHubPort):
    """GitHub stand-in for local development: real bare git repositories on disk, settings in a JSON file."""

    def __init__(self, root):
        self._root = Path(root) / "github"

    @classmethod
    def from_settings(cls, settings: Settings) -> "LocalGitHub":
        return cls(settings.local_state_dir)

    def repository_path(self, owner: str, name: str) -> Path:
        return self._root / owner / f"{name}.git"

    def repository_exists(self, owner: str, name: str) -> bool:
        return self.repository_path(owner, name).is_dir()

    def create_repository(self, owner: str, name: str, marker: str) -> bool:
        path = self.repository_path(owner, name)
        if path.is_dir():
            return self._resume(path, marker)
        path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init", "--quiet", "--bare", "--initial-branch", BRANCH, str(path)], check=True)
        (path / MARKER_FILE).write_text(marker)
        self._write_settings(path, {"repository": {}, "environments": {}})
        return True

    def delete_repository(self, owner: str, name: str) -> None:
        shutil.rmtree(self.repository_path(owner, name), ignore_errors=True)

    def set_repository_variables(self, owner: str, name: str, variables: dict[str, str]) -> None:
        self._update_settings(owner, name, "repository", dict(variables))

    def repository_variables(self, owner: str, name: str) -> dict[str, str]:
        return self._read_settings(self._existing(owner, name))["repository"]

    def set_environment(self, owner: str, name: str, environment: str, variables: dict[str, str]) -> None:
        path = self._existing(owner, name)
        settings = self._read_settings(path)
        settings["environments"][environment] = dict(variables)
        self._write_settings(path, settings)

    def environment(self, owner: str, name: str, environment: str) -> dict[str, str]:
        return self._read_settings(self._existing(owner, name))["environments"][environment]

    def commit_files(self, owner: str, name: str, files: dict[str, str], message: str) -> str:
        repository = GitPlumbing(self._existing(owner, name))
        with tempfile.TemporaryDirectory() as work:
            return repository.commit(files, message, Path(work) / "index")

    def _resume(self, path: Path, marker: str) -> bool:
        if (path / MARKER_FILE).read_text() != marker:
            raise RepositoryConflictError(f"{path.name} already exists and belongs to another request.")
        return False

    def _existing(self, owner: str, name: str) -> Path:
        path = self.repository_path(owner, name)
        if not path.is_dir():
            raise FileNotFoundError(f"Repository {owner}/{name} does not exist.")
        return path

    def _update_settings(self, owner: str, name: str, section: str, value: dict) -> None:
        path = self._existing(owner, name)
        settings = self._read_settings(path)
        settings[section] = value
        self._write_settings(path, settings)

    def _read_settings(self, path: Path) -> dict:
        return json.loads((path / SETTINGS_FILE).read_text())

    def _write_settings(self, path: Path, settings: dict) -> None:
        (path / SETTINGS_FILE).write_text(json.dumps(settings, indent=2, sort_keys=True))


class GitPlumbing:
    """Builds one commit with all files in a bare repository, like a tree + commit + ref update via the API."""

    def __init__(self, repository: Path):
        self._repository = repository

    def commit(self, files: dict[str, str], message: str, index_file: Path) -> str:
        environment = {**os.environ, **COMMITTER, "GIT_INDEX_FILE": str(index_file)}
        parents = self._parents()
        for parent in parents:
            self._git(environment, "read-tree", parent)
        for path, content in sorted(files.items()):
            blob = self._git(environment, "hash-object", "-w", "--stdin", stdin=content)
            self._git(environment, "update-index", "--add", "--cacheinfo", f"{FILE_MODE},{blob},{path}")
        tree = self._git(environment, "write-tree")
        parent_arguments = [argument for parent in parents for argument in ("-p", parent)]
        commit = self._git(environment, "commit-tree", tree, *parent_arguments, "-m", message)
        self._git(environment, "update-ref", f"refs/heads/{BRANCH}", commit)
        return commit

    def _parents(self) -> list[str]:
        head = subprocess.run(["git", "--git-dir", str(self._repository), "rev-parse", "--verify", "--quiet",
                               f"refs/heads/{BRANCH}"], capture_output=True, text=True,
                              check=False).stdout.strip()
        return [head] if head else []

    def _git(self, environment: dict, *arguments: str, stdin: str | None = None) -> str:
        completed = subprocess.run(["git", "--git-dir", str(self._repository), *arguments], input=stdin,
                                   capture_output=True, text=True, check=True, env=environment)
        return completed.stdout.strip()
