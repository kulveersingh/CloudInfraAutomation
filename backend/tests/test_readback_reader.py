import dataclasses
import json

import pytest

from app.readback.manifest import MANIFEST_PATH, Generator, ManifestSealer, ManifestSigner
from app.readback.reader import RepositoryReader
from app.readback.subjects import ReadBackSubject, ownership_properties

OWNER = "acme"
SIGNER = ManifestSigner({"k1": "secret"}, "k1")
REQUEST = {"value": "abc"}


class FakeSubject(ReadBackSubject):
    """Generates `input.json` (the request) and `out.txt` (the value, twice) into `demo-infra`."""

    kind = "project"
    input_file = "input.json"

    def __init__(self, request: dict | None = None, recorded_commit: str | None = None, suffix: str = "",
                 revision: int = 1, id: str = "demo", rejects_input: bool = False):
        self._request = request or REQUEST
        self._rejects_input = rejects_input
        self._recorded_commit = recorded_commit
        self._suffix = suffix
        self._revision = revision
        self._id = id

    @property
    def id(self):
        return self._id

    @property
    def revision(self):
        return self._revision

    @property
    def repository(self):
        return "demo-infra"

    @property
    def recorded_commit(self):
        return self._recorded_commit

    def recorded_request(self):
        return self._request

    def parse_input(self, text):
        document = json.loads(text)
        if self._rejects_input:
            raise ValueError("input.json has no 'name'")
        return document

    def regenerate(self, request):
        return {"input.json": json.dumps(request) + "\n", "out.txt": f"{request['value'] * 2}\n{self._suffix}"}


def publish(github, subject: FakeSubject | None = None, signer: ManifestSigner = SIGNER,
            properties: dict | None = None, files: dict | None = None) -> str:
    subject = subject or FakeSubject()
    github.create_repository(OWNER, subject.repository, marker="m")
    github.set_repository_properties(OWNER, subject.repository,
                                     ownership_properties(subject.kind, subject.id) if properties is None else properties)
    generated = subject.regenerate(subject.recorded_request())
    sealed = ManifestSealer(signer).seal(kind=subject.kind, id=subject.id, revision=subject.revision,
                                         generator=Generator("fake", "1"), input=subject.input_file, files=generated)
    return github.commit_files(OWNER, subject.repository, {**sealed, **(files or {})}, "generated")


def read(github, subject: FakeSubject | None = None) -> dict:
    return RepositoryReader.default(github, OWNER, SIGNER).read(subject or FakeSubject()).as_dict()


def blocking(result: dict) -> list[str]:
    return [finding["check"] for finding in result["findings"] if finding["severity"] == "blocking"]


def warnings(result: dict) -> list[str]:
    return [finding["check"] for finding in result["findings"] if finding["severity"] == "warning"]


# ---- verified ----

def test_sealed_repository_is_verified(local_github):
    sha = publish(local_github)
    result = read(local_github, FakeSubject(recorded_commit=sha))
    assert (result["verified"], result["findings"], result["commit_sha"]) == (True, [], sha)


def test_verified_result_returns_the_request_from_the_repository(local_github):
    sha = publish(local_github)
    assert read(local_github, FakeSubject(recorded_commit=sha))["request"] == REQUEST


def test_result_names_the_design(local_github):
    publish(local_github, FakeSubject(revision=3))
    assert read(local_github, FakeSubject(revision=3))["design"] == {"kind": "project", "id": "demo", "revision": 3}


def test_files_the_user_added_are_ignored(local_github):
    sha = publish(local_github, files={"docs/notes.md": "ours\n"})
    assert read(local_github, FakeSubject(recorded_commit=sha))["verified"] is True


def test_ownership_properties():
    assert ownership_properties("landing-zone", "4f0c") == {
        "cloudinfra-managed": "true", "cloudinfra-kind": "landing-zone", "cloudinfra-id": "4f0c"}


# ---- blocking ----

def test_missing_repository_blocks(local_github):
    result = read(local_github)
    assert (result["verified"], blocking(result), result["request"]) == (False, ["repository"], None)


def test_repository_without_commits_blocks(local_github):
    local_github.create_repository(OWNER, "demo-infra", marker="m")
    local_github.set_repository_properties(OWNER, "demo-infra", ownership_properties("project", "demo"))
    assert blocking(read(local_github)) == ["manifest"]


@pytest.mark.parametrize("properties", [{}, {"cloudinfra-managed": "false", "cloudinfra-kind": "project",
                                             "cloudinfra-id": "demo"},
                                        ownership_properties("landing-zone", "demo"),
                                        ownership_properties("project", "other")])
def test_repository_not_marked_as_ours_blocks(local_github, properties):
    publish(local_github, properties=properties)
    assert blocking(read(local_github)) == ["properties"]


def test_missing_manifest_blocks(local_github):
    local_github.create_repository(OWNER, "demo-infra", marker="m")
    local_github.set_repository_properties(OWNER, "demo-infra", ownership_properties("project", "demo"))
    local_github.commit_files(OWNER, "demo-infra", FakeSubject().regenerate(REQUEST), "copied by hand")
    result = read(local_github)
    assert (blocking(result), "manifest" in result["findings"][0]["message"]) == (["manifest"], True)


def test_unreadable_manifest_blocks(local_github):
    publish(local_github, files={MANIFEST_PATH: "{not json"})
    assert blocking(read(local_github)) == ["manifest"]


def test_manifest_signed_by_someone_else_blocks(local_github):
    publish(local_github, signer=ManifestSigner({"k1": "forged"}, "k1"))
    assert blocking(read(local_github)) == ["manifest"]


@pytest.mark.parametrize("expected", [FakeSubject(revision=2), FakeSubject(id="other")])
def test_manifest_for_another_design_blocks(local_github, expected):
    publish(local_github)
    local_github.set_repository_properties(OWNER, "demo-infra", ownership_properties("project", expected.id))
    assert blocking(read(local_github, expected)) == ["record"]


def test_hand_edited_file_blocks_with_a_diff(local_github):
    publish(local_github, files={"out.txt": "abcabc\nedited by hand\n"})
    result = read(local_github)
    [finding] = result["findings"]
    assert (blocking(result), [file["path"] for file in finding["files"]], result["request"]) == (
        ["integrity"], ["out.txt"], None)
    assert "+edited by hand" in finding["files"][0]["diff"]


def test_hand_edited_input_blocks(local_github):
    publish(local_github, files={"input.json": json.dumps({"value": "xyz"}) + "\n"})
    result = read(local_github)
    assert ([file["path"] for file in result["findings"][0]["files"]], blocking(result)) == (
        ["input.json"], ["integrity"])


def test_deleted_file_blocks(local_github):
    publish(local_github)
    original = SIGNER.verify(json.loads(local_github.read_files(OWNER, "demo-infra").files[MANIFEST_PATH]))
    tampered = dataclasses.replace(original, files={**original.files, "gone.txt": "sha256:00"})
    publish_raw(local_github, {MANIFEST_PATH: json.dumps(SIGNER.sign(tampered))})
    result = read(local_github)
    [finding] = result["findings"]
    assert (finding["check"], finding["files"]) == ("integrity", [{"path": "gone.txt", "diff": None}])


def test_diff_is_omitted_when_the_generator_changed_since(local_github):
    publish(local_github, files={"out.txt": "edited\n"})
    result = read(local_github, FakeSubject(suffix="new generator line\n"))
    assert result["findings"][0]["files"] == [{"path": "out.txt", "diff": None}]


def test_input_that_no_longer_parses_blocks(local_github):
    publish(local_github)
    result = read(local_github, FakeSubject(rejects_input=True))
    assert (blocking(result), result["findings"][0]["message"].endswith("input.json has no 'name'")) == (
        ["input"], True)


# ---- warnings ----

def test_commits_outside_the_platform_warn(local_github):
    publish(local_github)
    result = read(local_github, FakeSubject(recorded_commit="0" * 40))
    assert (result["verified"], warnings(result)) == (True, ["head"])


def test_generator_change_since_the_commit_warns(local_github):
    sha = publish(local_github)
    result = read(local_github, FakeSubject(recorded_commit=sha, suffix="new line\n"))
    [finding] = result["findings"]
    assert (result["verified"], finding["check"], finding["files"]) == (
        True, "regeneration", [{"path": "out.txt", "diff": None}])


def test_blocking_stops_later_checks(local_github):
    publish(local_github, files={"out.txt": "edited\n"})
    result = read(local_github, FakeSubject(recorded_commit="0" * 40))
    assert [finding["check"] for finding in result["findings"]] == ["integrity"]


def publish_raw(github, files: dict) -> str:
    return github.commit_files(OWNER, "demo-infra", files, "raw")
