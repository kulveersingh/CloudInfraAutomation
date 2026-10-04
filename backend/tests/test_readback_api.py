import json
import shutil

import pytest

from app.adapters.factory import AdapterFactory
from app.adapters.local_github import LocalGitHub
from app.provisioning.worker import Worker
from app.readback.manifest import MANIFEST_PATH, ManifestSigner
from app.synth.request import ProjectRequest
from tests.factories import request_dict
from tests.lz_factories import add_ou
from tests.test_lz_api import ALEX, BASE, SAM, approve, submitted

OWNER = "acme-platform"
LZ_REPOSITORY = "landing-zone-infra"
READ_BACK = f"{BASE}/repository:read-back"


def github(settings) -> LocalGitHub:
    return LocalGitHub(settings.local_state_dir)


def manifest(settings, repository: str) -> dict:
    document = json.loads(github(settings).read_files(OWNER, repository).files[MANIFEST_PATH])
    return ManifestSigner.from_settings(settings).verify(document).__dict__


def checks(result: dict) -> list[tuple[str, str]]:
    return [(finding["check"], finding["severity"]) for finding in result["findings"]]


# ---- landing zone ----

@pytest.fixture
def applied(client):
    return approve(client, submitted(client, edits=[add_ou("Tenants")])).json()


def test_landing_zone_read_back_needs_an_applied_design(client):
    assert client.get(READ_BACK, headers=ALEX).status_code == 404


def test_landing_zone_read_back_requires_a_platform_admin(client, applied):
    assert client.get(READ_BACK, headers=SAM).status_code == 403


def test_approval_seals_the_landing_zone_repository(client, settings, applied):
    sealed = manifest(settings, LZ_REPOSITORY)
    assert (sealed["kind"], sealed["id"], sealed["revision"], sealed["input"], sealed["generator"].name) == (
        "landing-zone", applied["id"], applied["version"], "design.json", "cloudinfra-landing-zone")


def test_manifest_covers_every_generated_file(client, settings, applied):
    files = github(settings).read_files(OWNER, LZ_REPOSITORY).files
    assert set(manifest(settings, LZ_REPOSITORY)["files"]) == set(files) - {MANIFEST_PATH}


def test_approval_marks_the_landing_zone_repository(client, settings, applied):
    assert github(settings).repository_properties(OWNER, LZ_REPOSITORY) == {
        "cloudinfra-managed": "true", "cloudinfra-kind": "landing-zone", "cloudinfra-id": applied["id"]}


def test_design_json_records_the_edits(client, settings, applied):
    design = json.loads(github(settings).read_files(OWNER, LZ_REPOSITORY).files["design.json"])
    assert design["edits"] == applied["edits"] == [{"op": "add_ou", "parent": "prod", "name": "Tenants"}]


def test_landing_zone_read_back_returns_the_applied_design(client, applied):
    result = client.get(READ_BACK, headers=ALEX).json()
    assert (result["verified"], result["findings"], result["commit_sha"], result["design"]) == (
        True, [], applied["commit_sha"],
        {"kind": "landing-zone", "id": applied["id"], "revision": applied["version"]})


def test_landing_zone_read_back_returns_answers_and_edits(client, applied):
    request = client.get(READ_BACK, headers=ALEX).json()["request"]
    assert request == {"answers": applied["answers"], "edits": applied["edits"]}


def test_landing_zone_read_back_follows_the_latest_version(client, applied):
    latest = approve(client, submitted(client)).json()
    result = client.get(READ_BACK, headers=ALEX).json()
    assert (result["verified"], result["design"]["revision"], result["request"]["edits"]) == (
        True, latest["version"], [])


def test_hand_edited_stack_blocks_landing_zone_read_back(client, settings, applied):
    path = "stacks/lz-structure.yaml"
    original = github(settings).read_files(OWNER, LZ_REPOSITORY).files[path]
    github(settings).commit_files(OWNER, LZ_REPOSITORY, {path: original + "# tweaked\n"}, "hand edit")
    result = client.get(READ_BACK, headers=ALEX).json()
    [finding] = result["findings"]
    assert (result["verified"], finding["check"], finding["files"][0]["path"], result["request"]) == (
        False, "integrity", path, None)
    assert "+# tweaked" in finding["files"][0]["diff"]


def test_extra_commits_only_warn(client, settings, applied):
    github(settings).commit_files(OWNER, LZ_REPOSITORY, {"docs/runbook.md": "notes\n"}, "add runbook")
    result = client.get(READ_BACK, headers=ALEX).json()
    assert (result["verified"], checks(result)) == (True, [("head", "warning")])


def test_repository_from_before_the_manifest_is_rejected(client, settings, applied):
    repository = github(settings)
    legacy = {path: text for path, text in repository.read_files(OWNER, LZ_REPOSITORY).files.items()
              if path != MANIFEST_PATH}
    properties = repository.repository_properties(OWNER, LZ_REPOSITORY)
    shutil.rmtree(repository.repository_path(OWNER, LZ_REPOSITORY))
    repository.create_repository(OWNER, LZ_REPOSITORY, marker="landing-zone")
    repository.set_repository_properties(OWNER, LZ_REPOSITORY, properties)
    repository.commit_files(OWNER, LZ_REPOSITORY, legacy, "generated before read-back")
    assert checks(client.get(READ_BACK, headers=ALEX).json()) == [("manifest", "blocking")]


# ---- projects ----

def provision(client, settings, session_factory) -> None:
    client.post("/v1/projects", json=request_dict(), headers={"Idempotency-Key": "k1"})
    factory = AdapterFactory()
    Worker(session_factory, factory.github(settings), factory.aws(settings), settings.github_owner,
           ManifestSigner.from_settings(settings)).process_one()


def project_read_back(client, name: str = "invoice-ingest"):
    return client.get(f"/v1/projects/{name}/repository:read-back")


def test_project_read_back_of_unknown_project(client):
    assert project_read_back(client, "nope").status_code == 404


def test_project_not_yet_provisioned_has_no_repository(client):
    client.post("/v1/projects", json=request_dict(), headers={"Idempotency-Key": "k1"})
    assert checks(project_read_back(client).json()) == [("repository", "blocking")]


def test_project_read_back_returns_the_request(client, settings, session_factory):
    provision(client, settings, session_factory)
    result = project_read_back(client).json()
    assert (result["verified"], result["findings"], result["design"], result["request"]) == (
        True, [], {"kind": "project", "id": "invoice-ingest", "revision": 1},
        ProjectRequest.model_validate(request_dict()).model_dump(mode="json"))


def test_provisioning_seals_and_marks_the_project_repository(client, settings, session_factory):
    provision(client, settings, session_factory)
    sealed = manifest(settings, "invoice-ingest-infra")
    assert ((sealed["kind"], sealed["id"], sealed["input"], sealed["generator"].name),
            github(settings).repository_properties(OWNER, "invoice-ingest-infra")) == (
        ("project", "invoice-ingest", "infra.json", "cloudinfra-synth"),
        {"cloudinfra-managed": "true", "cloudinfra-kind": "project", "cloudinfra-id": "invoice-ingest"})


def test_hand_edited_template_blocks_project_read_back(client, settings, session_factory):
    provision(client, settings, session_factory)
    github(settings).commit_files(OWNER, "invoice-ingest-infra", {"template.yaml": "Resources: {}\n"}, "hand edit")
    result = project_read_back(client).json()
    assert (result["verified"], checks(result), result["findings"][0]["files"][0]["path"]) == (
        False, [("integrity", "blocking")], "template.yaml")
