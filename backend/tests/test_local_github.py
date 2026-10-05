import subprocess

import pytest

from app.adapters.local_github import LocalGitHub
from app.adapters.ports import MergeConflictError, RepositoryArchivedError, RepositoryConflictError


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


# ---- branches and pull requests ----

def with_main(local_github) -> str:
    local_github.create_repository("acme", "demo-infra", marker="req-1")
    return local_github.commit_files("acme", "demo-infra", {"a.txt": "1", "b.txt": "2"}, "Initial")


def test_commit_to_a_new_branch_starts_from_main(local_github):
    main = with_main(local_github)
    local_github.commit_files("acme", "demo-infra", {"a.txt": "changed"}, "change", branch="feature")
    assert (local_github.read_files("acme", "demo-infra", branch="feature").files,
            local_github.read_files("acme", "demo-infra").commit_sha) == ({"a.txt": "changed", "b.txt": "2"}, main)


def test_reading_an_unknown_branch_is_empty(local_github):
    with_main(local_github)
    assert local_github.read_files("acme", "demo-infra", branch="nope").commit_sha is None


def test_delete_branch(local_github):
    with_main(local_github)
    local_github.commit_files("acme", "demo-infra", {"a.txt": "changed"}, "change", branch="feature")
    local_github.delete_branch("acme", "demo-infra", "feature")
    assert local_github.read_files("acme", "demo-infra", branch="feature").files == {}


def test_open_pull_request_numbers_them(local_github):
    with_main(local_github)
    local_github.commit_files("acme", "demo-infra", {"a.txt": "x"}, "change", branch="one")
    first = local_github.open_pull_request("acme", "demo-infra", "one", "First", "Body")
    second = local_github.open_pull_request("acme", "demo-infra", "one", "Second", "Body")
    assert ((first.number, first.url), second.number) == (
        (1, "https://github.com/acme/demo-infra/pull/1"), 2)


def test_pull_request_details_are_kept(local_github):
    with_main(local_github)
    local_github.commit_files("acme", "demo-infra", {"a.txt": "x"}, "change", branch="one")
    local_github.open_pull_request("acme", "demo-infra", "one", "Title", "Body text")
    assert local_github.pull_request("acme", "demo-infra", 1) == {
        "number": 1, "branch": "one", "title": "Title", "body": "Body text", "state": "open", "merge_commit": None}


def test_merge_fast_forwards_main_and_deletes_the_branch(local_github):
    with_main(local_github)
    head = local_github.commit_files("acme", "demo-infra", {"a.txt": "x"}, "change", branch="one")
    local_github.open_pull_request("acme", "demo-infra", "one", "Title", "Body")
    merged = local_github.merge_pull_request("acme", "demo-infra", 1)
    assert (merged, local_github.read_files("acme", "demo-infra").files["a.txt"],
            local_github.pull_request("acme", "demo-infra", 1)["state"],
            local_github.pull_request("acme", "demo-infra", 1)["merge_commit"],
            local_github.read_files("acme", "demo-infra", branch="one").commit_sha) == (head, "x", "merged", head, None)


def test_merge_refuses_when_main_moved(local_github):
    with_main(local_github)
    local_github.commit_files("acme", "demo-infra", {"a.txt": "x"}, "change", branch="one")
    local_github.open_pull_request("acme", "demo-infra", "one", "Title", "Body")
    local_github.commit_files("acme", "demo-infra", {"c.txt": "3"}, "someone else")
    with pytest.raises(MergeConflictError):
        local_github.merge_pull_request("acme", "demo-infra", 1)


def test_close_pull_request_keeps_main_and_deletes_the_branch(local_github):
    main = with_main(local_github)
    local_github.commit_files("acme", "demo-infra", {"a.txt": "x"}, "change", branch="one")
    local_github.open_pull_request("acme", "demo-infra", "one", "Title", "Body")
    local_github.close_pull_request("acme", "demo-infra", 1)
    assert (local_github.pull_request("acme", "demo-infra", 1)["state"],
            local_github.read_files("acme", "demo-infra").commit_sha,
            local_github.read_files("acme", "demo-infra", branch="one").commit_sha) == ("closed", main, None)


@pytest.mark.parametrize("action", ["merge_pull_request", "close_pull_request"])
def test_only_open_pull_requests_can_be_merged_or_closed(local_github, action):
    with_main(local_github)
    local_github.commit_files("acme", "demo-infra", {"a.txt": "x"}, "change", branch="one")
    local_github.open_pull_request("acme", "demo-infra", "one", "Title", "Body")
    local_github.close_pull_request("acme", "demo-infra", 1)
    with pytest.raises(MergeConflictError, match="closed"):
        getattr(local_github, action)("acme", "demo-infra", 1)


def test_unknown_pull_request(local_github):
    with_main(local_github)
    with pytest.raises(KeyError):
        local_github.pull_request("acme", "demo-infra", 7)


def test_deleting_a_missing_branch_does_nothing(local_github):
    main = with_main(local_github)
    local_github.delete_branch("acme", "demo-infra", "gone")
    assert local_github.read_files("acme", "demo-infra").commit_sha == main


def test_merging_one_pull_request_leaves_the_others_open(local_github):
    with_main(local_github)
    local_github.commit_files("acme", "demo-infra", {"a.txt": "x"}, "one", branch="one")
    local_github.commit_files("acme", "demo-infra", {"a.txt": "y"}, "two", branch="two")
    local_github.open_pull_request("acme", "demo-infra", "one", "One", "Body")
    local_github.open_pull_request("acme", "demo-infra", "two", "Two", "Body")
    local_github.merge_pull_request("acme", "demo-infra", 2)
    assert local_github.pull_request("acme", "demo-infra", 1)["state"] == "open"


# ---- teardown support ----

def test_commit_can_delete_paths(local_github):
    with_main(local_github)
    local_github.commit_files("acme", "demo-infra", {"c.txt": "3"}, "change", deleted=["b.txt"])
    assert local_github.read_files("acme", "demo-infra").files == {"a.txt": "1", "c.txt": "3"}


def test_delete_environment(local_github):
    with_main(local_github)
    local_github.set_environment("acme", "demo-infra", "dev", {"A": "1"})
    local_github.delete_environment("acme", "demo-infra", "dev")
    with pytest.raises(KeyError):
        local_github.environment("acme", "demo-infra", "dev")


def test_deleting_a_missing_environment_does_nothing(local_github):
    with_main(local_github)
    local_github.delete_environment("acme", "demo-infra", "dev")


def test_archived_repositories_refuse_commits(local_github):
    with_main(local_github)
    local_github.archive_repository("acme", "demo-infra")
    with pytest.raises(RepositoryArchivedError):
        local_github.commit_files("acme", "demo-infra", {"a.txt": "x"}, "change")


def test_unarchived_repositories_accept_commits_again(local_github):
    with_main(local_github)
    local_github.archive_repository("acme", "demo-infra")
    local_github.unarchive_repository("acme", "demo-infra")
    local_github.commit_files("acme", "demo-infra", {"a.txt": "x"}, "change")
    assert (local_github.read_files("acme", "demo-infra").files["a.txt"],
            local_github.is_archived("acme", "demo-infra")) == ("x", False)
