import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from app.adapters.ports import (
    DEFAULT_BRANCH,
    GitHubPort,
    MergeConflictError,
    PullRequest,
    RepositoryArchivedError,
    RepositoryConflictError,
    RepositorySnapshot,
)
from app.config import Settings

BRANCH = DEFAULT_BRANCH
PULL_REQUEST_URL = "https://github.com/{owner}/{name}/pull/{number}"
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
        self._write_settings(path, {"repository": {}, "environments": {}, "properties": {}, "pull_requests": []})
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

    def commit_files(self, owner: str, name: str, files: dict[str, str], message: str, branch: str = BRANCH,
                     deleted: tuple[str, ...] | list[str] = ()) -> str:
        if self.is_archived(owner, name):
            raise RepositoryArchivedError(f"{owner}/{name} is archived.")
        repository = GitPlumbing(self._existing(owner, name))
        with tempfile.TemporaryDirectory() as work:
            return repository.commit(files, message, Path(work) / "index", branch, deleted)

    def delete_environment(self, owner: str, name: str, environment: str) -> None:
        path = self._existing(owner, name)
        settings = self._read_settings(path)
        settings["environments"].pop(environment, None)
        self._write_settings(path, settings)

    def archive_repository(self, owner: str, name: str) -> None:
        self._set_archived(owner, name, True)

    def unarchive_repository(self, owner: str, name: str) -> None:
        self._set_archived(owner, name, False)

    def is_archived(self, owner: str, name: str) -> bool:
        return self._read_settings(self._existing(owner, name)).get("archived", False)

    def _set_archived(self, owner: str, name: str, archived: bool) -> None:
        path = self._existing(owner, name)
        settings = self._read_settings(path)
        settings["archived"] = archived
        self._write_settings(path, settings)

    def read_files(self, owner: str, name: str, branch: str = BRANCH) -> RepositorySnapshot:
        return GitPlumbing(self._existing(owner, name)).snapshot(branch)

    def delete_branch(self, owner: str, name: str, branch: str) -> None:
        GitPlumbing(self._existing(owner, name)).delete_branch(branch)

    def open_pull_request(self, owner: str, name: str, branch: str, title: str, body: str) -> PullRequest:
        path = self._existing(owner, name)
        settings = self._read_settings(path)
        pull_requests = settings.setdefault("pull_requests", [])
        number = len(pull_requests) + 1
        pull_requests.append({"number": number, "branch": branch, "title": title, "body": body, "state": "open",
                              "merge_commit": None})
        self._write_settings(path, settings)
        return PullRequest(number=number, url=PULL_REQUEST_URL.format(owner=owner, name=name, number=number))

    def pull_request(self, owner: str, name: str, number: int) -> dict:
        pull_requests = self._read_settings(self._existing(owner, name)).get("pull_requests", [])
        found = next((pull_request for pull_request in pull_requests if pull_request["number"] == number), None)
        if found is None:
            raise KeyError(f"Pull request #{number} does not exist in {owner}/{name}.")
        return found

    def merge_pull_request(self, owner: str, name: str, number: int) -> str:
        pull_request = self._open(owner, name, number)
        repository = GitPlumbing(self._existing(owner, name))
        head = repository.fast_forward(pull_request["branch"])
        repository.delete_branch(pull_request["branch"])
        self._set_pull_request(owner, name, number, state="merged", merge_commit=head)
        return head

    def close_pull_request(self, owner: str, name: str, number: int) -> None:
        pull_request = self._open(owner, name, number)
        GitPlumbing(self._existing(owner, name)).delete_branch(pull_request["branch"])
        self._set_pull_request(owner, name, number, state="closed")

    def _open(self, owner: str, name: str, number: int) -> dict:
        pull_request = self.pull_request(owner, name, number)
        if pull_request["state"] != "open":
            raise MergeConflictError(f"Pull request #{number} is {pull_request['state']}.")
        return pull_request

    def _set_pull_request(self, owner: str, name: str, number: int, **changes) -> None:
        path = self._existing(owner, name)
        settings = self._read_settings(path)
        for pull_request in settings["pull_requests"]:
            if pull_request["number"] == number:
                pull_request.update(changes)
        self._write_settings(path, settings)

    def set_repository_properties(self, owner: str, name: str, properties: dict[str, str]) -> None:
        self._update_settings(owner, name, "properties", dict(properties))

    def repository_properties(self, owner: str, name: str) -> dict[str, str]:
        return self._read_settings(self._existing(owner, name)).get("properties", {})

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

    def commit(self, files: dict[str, str], message: str, index_file: Path, branch: str = BRANCH,
               deleted: tuple[str, ...] | list[str] = ()) -> str:
        environment = {**os.environ, **COMMITTER, "GIT_INDEX_FILE": str(index_file)}
        parents = self._parents(branch) or self._parents(BRANCH)
        for parent in parents:
            self._git(environment, "read-tree", parent)
        for path, content in sorted(files.items()):
            blob = self._git(environment, "hash-object", "-w", "--stdin", stdin=content)
            self._git(environment, "update-index", "--add", "--cacheinfo", f"{FILE_MODE},{blob},{path}")
        if deleted:  # a zero mode and object id removes the entry; this works without a work tree
            removals = "".join(f"0 {'0' * 40}\t{path}\n" for path in deleted)
            self._git(environment, "update-index", "--index-info", stdin=removals)
        tree = self._git(environment, "write-tree")
        parent_arguments = [argument for parent in parents for argument in ("-p", parent)]
        commit = self._git(environment, "commit-tree", tree, *parent_arguments, "-m", message)
        self._git(environment, "update-ref", f"refs/heads/{branch}", commit)
        return commit

    def delete_branch(self, branch: str) -> None:
        if self._parents(branch):
            self._git(dict(os.environ), "update-ref", "-d", f"refs/heads/{branch}")

    def fast_forward(self, branch: str) -> str:
        """Moves the default branch to the branch head; refuses when the default branch moved since."""
        [main], [head] = self._parents(BRANCH), self._parents(branch)
        ancestor = subprocess.run(["git", "--git-dir", str(self._repository), "merge-base", "--is-ancestor", main,
                                   head], check=False).returncode == 0
        if not ancestor:
            raise MergeConflictError(f"{BRANCH} has commits that {branch} does not; the change must be redone.")
        self._git(dict(os.environ), "update-ref", f"refs/heads/{BRANCH}", head)
        return head

    def snapshot(self, branch: str = BRANCH) -> RepositorySnapshot:
        parents = self._parents(branch)
        if not parents:
            return RepositorySnapshot(commit_sha=None, files={})
        environment = dict(os.environ)
        paths = self._git(environment, "ls-tree", "-r", "-z", "--name-only", parents[0]).split("\0")
        return RepositorySnapshot(commit_sha=parents[0], files={
            path: self._git(environment, "show", f"{parents[0]}:{path}", strip=False) for path in paths if path})

    def _parents(self, branch: str = BRANCH) -> list[str]:
        head = subprocess.run(["git", "--git-dir", str(self._repository), "rev-parse", "--verify", "--quiet",
                               f"refs/heads/{branch}"], capture_output=True, text=True,
                              check=False).stdout.strip()
        return [head] if head else []

    def _git(self, environment: dict, *arguments: str, stdin: str | None = None, strip: bool = True) -> str:
        completed = subprocess.run(["git", "--git-dir", str(self._repository), *arguments], input=stdin,
                                   capture_output=True, text=True, check=True, env=environment)
        return completed.stdout.strip() if strip else completed.stdout
