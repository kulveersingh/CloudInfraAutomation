import json

import pytest

from app.adapters.factory import AdapterFactory
from app.adapters.local_aws import LocalAws
from app.adapters.local_github import LocalGitHub
from app.provisioning.worker import Worker
from app.readback.manifest import MANIFEST_PATH, ManifestSigner
from tests.factories import request_dict

OWNER = "acme-platform"
REPOSITORY = "invoice-ingest-infra"
PROJECT = "/v1/projects/invoice-ingest"
JORDAN = {"X-Actor": "jordan", "X-Roles": "developer"}


def github(settings) -> LocalGitHub:
    return LocalGitHub(settings.local_state_dir)


def run_worker(settings, session_factory) -> None:
    factory = AdapterFactory()
    Worker(session_factory, factory.github(settings), factory.clouds(settings), settings.github_owner,
           ManifestSigner.from_settings(settings)).process_one()


@pytest.fixture
def provisioned(client, settings, session_factory) -> dict:
    """The project as read back after provisioning: its request and the commit it was read at."""
    client.post("/v1/projects", json=request_dict(), headers={"Idempotency-Key": "k1"})
    run_worker(settings, session_factory)
    return client.get(f"{PROJECT}/repository:read-back").json()


def with_table(request: dict) -> dict:
    return {**request, "resources": [*request["resources"], {"id": "orders", "type": "dynamodb.table",
                                                             "config": {}}]}


def body(provisioned: dict, request: dict | None = None, **extra) -> dict:
    return {"request": request or with_table(provisioned["request"]), "base_commit": provisioned["commit_sha"],
            **extra}


def preview(client, provisioned, request=None):
    return client.post(f"{PROJECT}/changes:preview", json=body(provisioned, request))


def create(client, provisioned, request=None, **extra):
    return client.post(f"{PROJECT}/changes", json=body(provisioned, request, **extra), headers=JORDAN)


def opened(client, settings, session_factory, provisioned, request=None, **extra) -> dict:
    change = create(client, provisioned, request, **extra).json()
    run_worker(settings, session_factory)
    return client.get(f"{PROJECT}/changes/{change['id']}").json()


def without_processor(request: dict) -> dict:
    return {**request, "resources": [resource for resource in request["resources"] if resource["id"] != "processor"],
            "connections": []}


# ---- preview ----

def test_preview_summarises_an_added_service(client, provisioned):
    summary = preview(client, provisioned).json()["summary"]
    assert (summary["added_services"], summary["removed_services"], summary["changed_services"],
            summary["added_environments"]) == (["orders"], [], [], [])


def test_preview_lists_the_files_that_change(client, provisioned):
    assert preview(client, provisioned).json()["summary"]["changed_files"] == ["infra.json", "template.yaml"]


def test_preview_includes_the_generated_files(client, provisioned):
    assert "OrdersTable" in preview(client, provisioned).json()["files"]["template.yaml"]


def test_preview_says_whether_removed_services_are_retained(client, provisioned):
    request = without_processor(provisioned["request"])
    request["resources"] = [{"id": "archive", "type": "sqs.queue"}]
    summary = preview(client, provisioned, request).json()["summary"]
    assert (summary["removed_services"], summary["added_services"]) == (
        [{"id": "uploads", "type": "s3.bucket", "retained": True},
         {"id": "processor", "type": "lambda.function", "retained": False}], ["archive"])


def test_preview_lists_changed_services_and_added_environments(client, provisioned):
    request = {**provisioned["request"], "environments": [*provisioned["request"]["environments"], "sandbox"]}
    request["resources"] = [dict(resource) for resource in request["resources"]]
    request["resources"][1]["config"] = {"memory_mb": 512}
    summary = preview(client, provisioned, request).json()["summary"]
    assert (summary["changed_services"], summary["added_environments"]) == (["processor"], ["sandbox"])


def test_preview_rejects_locked_fields(client, provisioned):
    request = with_table(provisioned["request"])
    request["ownership"] = {**request["ownership"], "data_classification": "restricted"}
    response = preview(client, provisioned, request)
    assert (response.status_code, response.json()["detail"]) == (422, "The data classification cannot change.")


def test_preview_rejects_invalid_requests(client, provisioned):
    request = with_table(provisioned["request"])
    request["resources"][-1]["config"] = {"memory": 1}
    assert preview(client, provisioned, request).status_code == 422


# ---- create ----

def test_create_queues_a_change_at_the_next_revision(client, provisioned):
    response = create(client, provisioned)
    change = response.json()
    assert (response.status_code, change["state"], change["revision"], change["created_by"], change["base_commit"],
            change["pull_request"], bool(change["job_id"])) == (
        202, "queued", 2, "jordan", provisioned["commit_sha"], None, True)


def test_create_records_the_summary(client, provisioned):
    assert create(client, provisioned).json()["summary"]["added_services"] == ["orders"]


def test_create_needs_the_commit_the_project_was_read_at(client, provisioned):
    response = client.post(f"{PROJECT}/changes", json={**body(provisioned), "base_commit": "0" * 40}, headers=JORDAN)
    assert (response.status_code, response.json()["detail"]) == (
        409, "The repository changed since you loaded it: load the project again and redo the change.")


def test_create_refuses_when_the_repository_moved(client, settings, provisioned):
    github(settings).commit_files(OWNER, REPOSITORY, {"docs/notes.md": "x\n"}, "someone else")
    assert create(client, provisioned).status_code == 409


def test_only_one_open_change_per_project(client, provisioned):
    create(client, provisioned)
    response = create(client, provisioned)
    assert (response.status_code, response.json()["detail"]) == (
        409, "Change revision 2 is still open: merge or close it first.")


def test_removing_services_that_are_deleted_needs_confirmation(client, provisioned):
    response = create(client, provisioned, without_processor(provisioned["request"]))
    assert (response.status_code, response.json()["detail"]) == (
        422, "Removing processor deletes its resources: confirm the removal.")


def test_confirmed_removal_is_accepted(client, provisioned):
    assert create(client, provisioned, without_processor(provisioned["request"]),
                  confirm_removals=True).status_code == 202


def test_retained_removals_need_no_confirmation(client, provisioned):
    request = {**provisioned["request"], "resources": [provisioned["request"]["resources"][1]], "connections": []}
    assert create(client, provisioned, request).status_code == 202


def test_nothing_changed(client, provisioned):
    response = create(client, provisioned, provisioned["request"])
    assert (response.status_code, response.json()["detail"]) == (422, "Nothing changed.")


def test_project_must_be_active(client):
    client.post("/v1/projects", json=request_dict(), headers={"Idempotency-Key": "k1"})
    response = client.post(f"{PROJECT}/changes", json={"request": with_table(request_dict()), "base_commit": "x"},
                           headers=JORDAN)
    assert (response.status_code, response.json()["detail"]) == (
        409, "Project 'invoice-ingest' is provisioning; it can change once it is active.")


def test_unknown_project(client):
    response = client.post("/v1/projects/nope/changes", json={"request": request_dict(), "base_commit": "x"})
    assert response.status_code == 404


# ---- the change job ----

def test_change_job_opens_a_pull_request(client, settings, session_factory, provisioned):
    change = opened(client, settings, session_factory, provisioned)
    assert (change["state"], change["branch"], change["pull_request"]) == (
        "open", "cloudinfra/change-2",
        {"number": 1, "url": "https://github.com/acme-platform/invoice-ingest-infra/pull/1"})


def test_pull_request_describes_the_change(client, settings, session_factory, provisioned):
    opened(client, settings, session_factory, provisioned)
    pull_request = github(settings).pull_request(OWNER, REPOSITORY, 1)
    assert (pull_request["title"], "orders" in pull_request["body"], "template.yaml" in pull_request["body"]) == (
        "Change infrastructure: revision 2", True, True)


def test_branch_holds_the_regenerated_files_sealed_at_the_new_revision(client, settings, session_factory, provisioned):
    opened(client, settings, session_factory, provisioned)
    files = github(settings).read_files(OWNER, REPOSITORY, branch="cloudinfra/change-2").files
    manifest = ManifestSigner.from_settings(settings).verify(json.loads(files[MANIFEST_PATH]))
    assert (manifest.revision, "OrdersTable" in files["template.yaml"]) == (2, True)


def test_main_is_unchanged_until_the_merge(client, settings, session_factory, provisioned):
    opened(client, settings, session_factory, provisioned)
    assert github(settings).read_files(OWNER, REPOSITORY).commit_sha == provisioned["commit_sha"]


def test_change_job_bootstraps_and_configures_added_environments(client, settings, session_factory, provisioned):
    request = {**with_table(provisioned["request"]), "environments": [*provisioned["request"]["environments"],
                                                                      "sandbox"]}
    opened(client, settings, session_factory, provisioned, request)
    stacks = LocalAws(settings.local_state_dir).stacks()
    assert ([stack["account"] for stack in stacks if stack["environment"] == "sandbox"],
            github(settings).environment(OWNER, REPOSITORY, "sandbox")["AWS_ACCOUNT_ID"]) == (
        ["111111111111"], "111111111111")


def test_change_job_steps(client, settings, session_factory, provisioned):
    change = create(client, provisioned).json()
    run_worker(settings, session_factory)
    steps = [step["name"] for step in client.get(f"/v1/jobs/{change['job_id']}").json()["steps"]]
    assert steps == ["outputs:dev:us-east-1", "outputs:test:us-east-1", "outputs:stage:us-east-1",
                     "outputs:prod:us-east-1", "configure_environments", "commit_branch", "open_pull_request"]


def test_failed_change_job_removes_the_branch(client, settings, session_factory, provisioned, monkeypatch):
    def refuse(*arguments, **keywords):
        raise RuntimeError("GitHub is down")

    monkeypatch.setattr(LocalGitHub, "open_pull_request", refuse)
    change = opened(client, settings, session_factory, provisioned)
    assert (change["state"], github(settings).read_files(OWNER, REPOSITORY, branch="cloudinfra/change-2").commit_sha,
            create(client, provisioned).status_code) == ("failed", None, 202)


# ---- merge and close ----

def test_merge_records_the_new_revision(client, settings, session_factory, provisioned):
    change = opened(client, settings, session_factory, provisioned)
    merged = client.post(f"{PROJECT}/changes/{change['id']}:merge").json()
    read_back = client.get(f"{PROJECT}/repository:read-back").json()
    assert (merged["state"], merged["merge_commit"] == read_back["commit_sha"], read_back["verified"],
            read_back["findings"], read_back["design"]["revision"], read_back["request"]["resources"][-1]["id"]) == (
        "merged", True, True, [], 2, "orders")


def test_project_lists_its_revision_and_open_change(client, settings, session_factory, provisioned):
    change = opened(client, settings, session_factory, provisioned)
    [project] = client.get("/v1/projects").json()
    assert (project["revision"], project["open_change"]) == (1, {
        "id": change["id"], "revision": 2, "state": "open", "pull_request": change["pull_request"]})


def test_merged_change_is_no_longer_open(client, settings, session_factory, provisioned):
    change = opened(client, settings, session_factory, provisioned)
    client.post(f"{PROJECT}/changes/{change['id']}:merge")
    [project] = client.get("/v1/projects").json()
    assert (project["revision"], project["open_change"]) == (2, None)


def test_a_later_change_builds_on_the_merged_revision(client, settings, session_factory, provisioned):
    change = opened(client, settings, session_factory, provisioned)
    client.post(f"{PROJECT}/changes/{change['id']}:merge")
    current = client.get(f"{PROJECT}/repository:read-back").json()
    request = {**current["request"], "resources": [*current["request"]["resources"],
                                                   {"id": "jobs", "type": "sqs.queue", "config": {}}]}
    assert opened(client, settings, session_factory, current, request)["revision"] == 3


def test_close_keeps_the_project(client, settings, session_factory, provisioned):
    change = opened(client, settings, session_factory, provisioned)
    closed = client.post(f"{PROJECT}/changes/{change['id']}:close").json()
    [project] = client.get("/v1/projects").json()
    assert (closed["state"], project["revision"], project["open_change"],
            create(client, provisioned).status_code) == ("closed", 1, None, 202)


def test_merge_refuses_when_main_moved(client, settings, session_factory, provisioned):
    change = opened(client, settings, session_factory, provisioned)
    github(settings).commit_files(OWNER, REPOSITORY, {"docs/notes.md": "x\n"}, "someone else")
    response = client.post(f"{PROJECT}/changes/{change['id']}:merge")
    assert (response.status_code, client.get(f"{PROJECT}/changes/{change['id']}").json()["state"]) == (409, "open")


@pytest.mark.parametrize("action", ["merge", "close"])
def test_only_open_changes_can_be_merged_or_closed(client, provisioned, action):
    change = create(client, provisioned).json()
    response = client.post(f"{PROJECT}/changes/{change['id']}:{action}")
    assert (response.status_code, response.json()["detail"]) == (409, "Change revision 2 is queued, not open.")


def test_list_changes_newest_first(client, settings, session_factory, provisioned):
    first = opened(client, settings, session_factory, provisioned)
    client.post(f"{PROJECT}/changes/{first['id']}:close")
    second = create(client, provisioned).json()
    assert [change["id"] for change in client.get(f"{PROJECT}/changes").json()] == [second["id"], first["id"]]


def test_unknown_change(client, provisioned):
    assert client.get(f"{PROJECT}/changes/00000000-0000-0000-0000-000000000000").status_code == 404


def test_change_of_another_project_is_not_found(client, settings, session_factory, provisioned):
    change = create(client, provisioned).json()
    assert client.get(f"/v1/projects/other/changes/{change['id']}").status_code == 404
