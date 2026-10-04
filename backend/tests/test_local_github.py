import subprocess

import pytest

from app.adapters.local_github import LocalGitHub
from app.adapters.ports import RepositoryConflictError


def git(local_github: LocalGitHub, *args: str) -> str:
    repository = local_github.repository_path("acme", "demo-infra")
    return subprocess.run(["git", "--git-dir", str(repository), *args], capture_output=True, text=True,
                          check=True).stdout


def test_create_repository_reports_creation(local_github):
    assert local_github.create_repository("acme", "demo-infra", marker="req-1") is True


def test_repository_is_a_bare_git_repository(local_github):
    local_github.create_repository("acme", "demo-infra", marker="req-1")
    assert git(local_github, "rev-parse", "--is-bare-repository").strip() == "true"


def test_create_repository_again_with_same_marker_resumes(local_github):
    local_github.create_repository("acme", "demo-infra", marker="req-1")
    assert local_github.create_repository("acme", "demo-infra", marker="req-1") is False


def test_create_repository_owned_by_other_request(local_github):
    local_github.create_repository("acme", "demo-infra", marker="req-1")
    with pytest.raises(RepositoryConflictError):
        local_github.create_repository("acme", "demo-infra", marker="req-2")


def test_commit_creates_a_single_commit(local_github):
    local_github.create_repository("acme", "demo-infra", marker="req-1")
    local_github.commit_files("acme", "demo-infra", {"a.txt": "1", "dir/b.txt": "2"}, "Initial infrastructure")
    assert len(git(local_github, "log", "--oneline", "main").splitlines()) == 1


def test_commit_contains_all_files(local_github):
    local_github.create_repository("acme", "demo-infra", marker="req-1")
    local_github.commit_files("acme", "demo-infra", {"a.txt": "1", "dir/b.txt": "2"}, "Initial infrastructure")
    assert git(local_github, "ls-tree", "-r", "--name-only", "main").split() == ["a.txt", "dir/b.txt"]


def test_commit_returns_sha(local_github):
    local_github.create_repository("acme", "demo-infra", marker="req-1")
    sha = local_github.commit_files("acme", "demo-infra", {"a.txt": "1"}, "Initial infrastructure")
    assert sha == git(local_github, "rev-parse", "main").strip()


def test_second_commit_builds_on_first(local_github):
    local_github.create_repository("acme", "demo-infra", marker="req-1")
    local_github.commit_files("acme", "demo-infra", {"a.txt": "1"}, "one")
    local_github.commit_files("acme", "demo-infra", {"a.txt": "2"}, "two")
    assert len(git(local_github, "log", "--oneline", "main").splitlines()) == 2


def test_commit_to_unknown_repository(local_github):
    with pytest.raises(FileNotFoundError):
        local_github.commit_files("acme", "missing", {"a.txt": "1"}, "one")


def test_environment_variables_are_stored(local_github):
    local_github.create_repository("acme", "demo-infra", marker="req-1")
    local_github.set_environment("acme", "demo-infra", "prod", {"AWS_ACCOUNT_ID": "555555555555"})
    assert local_github.environment("acme", "demo-infra", "prod") == {"AWS_ACCOUNT_ID": "555555555555"}


def test_repository_variables_are_stored(local_github):
    local_github.create_repository("acme", "demo-infra", marker="req-1")
    local_github.set_repository_variables("acme", "demo-infra", {"PROJECT_NAME": "demo"})
    assert local_github.repository_variables("acme", "demo-infra") == {"PROJECT_NAME": "demo"}


def test_delete_repository(local_github):
    local_github.create_repository("acme", "demo-infra", marker="req-1")
    local_github.delete_repository("acme", "demo-infra")
    assert not local_github.repository_exists("acme", "demo-infra")


def test_delete_missing_repository_is_harmless(local_github):
    assert local_github.delete_repository("acme", "demo-infra") is None


def test_read_files_returns_head_tree_and_sha(local_github):
    local_github.create_repository("acme", "demo-infra", marker="req-1")
    sha = local_github.commit_files("acme", "demo-infra", {"a.txt": "1", "dir/b.txt": "two\n"}, "Initial")
    snapshot = local_github.read_files("acme", "demo-infra")
    assert (snapshot.commit_sha, snapshot.files) == (sha, {"a.txt": "1", "dir/b.txt": "two\n"})


def test_read_files_sees_the_latest_commit(local_github):
    local_github.create_repository("acme", "demo-infra", marker="req-1")
    local_github.commit_files("acme", "demo-infra", {"a.txt": "1"}, "one")
    local_github.commit_files("acme", "demo-infra", {"a.txt": "2", "b.txt": "3"}, "two")
    assert local_github.read_files("acme", "demo-infra").files == {"a.txt": "2", "b.txt": "3"}


def test_read_files_of_an_empty_repository(local_github):
    local_github.create_repository("acme", "demo-infra", marker="req-1")
    snapshot = local_github.read_files("acme", "demo-infra")
    assert (snapshot.commit_sha, snapshot.files) == (None, {})


def test_read_files_of_unknown_repository(local_github):
    with pytest.raises(FileNotFoundError):
        local_github.read_files("acme", "missing")


def test_repository_properties_are_stored(local_github):
    local_github.create_repository("acme", "demo-infra", marker="req-1")
    local_github.set_repository_properties("acme", "demo-infra", {"cloudinfra-managed": "true"})
    assert local_github.repository_properties("acme", "demo-infra") == {"cloudinfra-managed": "true"}


def test_new_repository_has_no_properties(local_github):
    local_github.create_repository("acme", "demo-infra", marker="req-1")
    assert local_github.repository_properties("acme", "demo-infra") == {}
