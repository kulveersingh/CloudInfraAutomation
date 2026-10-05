import json
from datetime import UTC, datetime, timedelta

import pytest

from app.adapters.factory import AdapterFactory
from app.adapters.local_aws import LocalAws
from app.adapters.local_backup import LocalBackup
from app.adapters.local_github import LocalGitHub
from app.config import Settings
from app.provisioning.worker import Worker
from app.readback.manifest import ManifestSigner
from tests.factories import TEST_DATABASE_URL, request_dict

OWNER = "acme-platform"
REPOSITORY = "invoice-ingest-infra"
PROJECT = "/v1/projects/invoice-ingest"
BACKUP_ACCOUNT = "999999999999"
DEV_ACCOUNT = "222222222222"
JORDAN = {"X-Actor": "jordan", "X-Roles": "developer"}
SAM = {"X-Actor": "sam", "X-Roles": "reviewer"}
ALEX = {"X-Actor": "alex", "X-Roles": "platform-admin,reviewer"}


@pytest.fixture
def settings(tmp_path):
    return Settings(database_url=TEST_DATABASE_URL, local_state_dir=str(tmp_path), worker_poll_seconds=0,
                    backup_account_id=BACKUP_ACCOUNT)


def github(settings) -> LocalGitHub:
    return LocalGitHub(settings.local_state_dir)


def backup(settings) -> LocalBackup:
    return LocalBackup(settings.local_state_dir, BACKUP_ACCOUNT)


def aws(settings) -> LocalAws:
    return LocalAws(settings.local_state_dir)


def drain(settings, session_factory) -> None:
    factory = AdapterFactory()
    worker = Worker(session_factory, factory.github(settings), factory.clouds(settings), settings.github_owner,
                    ManifestSigner.from_settings(settings))
    while worker.process_one():
        pass


@pytest.fixture
def provisioned(client, settings, session_factory) -> None:
    client.post("/v1/projects", json=request_dict(), headers={"Idempotency-Key": "k1"})
    drain(settings, session_factory)


def preview(client, scope="environment", environments=("dev",)):
    return client.post(f"{PROJECT}/teardowns:preview", json={"scope": scope, "environments": list(environments)})


def request(client, scope="environment", environments=("dev",), confirmation="invoice-ingest", headers=JORDAN):
    return client.post(f"{PROJECT}/teardowns", json={"scope": scope, "environments": list(environments),
                                                     "confirmation": confirmation}, headers=headers)


def decide(client, teardown_id, environment, decision="approve", headers=SAM):
    return client.post(f"{PROJECT}/teardowns/{teardown_id}/environments/{environment}:{decision}",
                       json={"comment": "ok"}, headers=headers)


def get(client, teardown_id) -> dict:
    return client.get(f"{PROJECT}/teardowns/{teardown_id}").json()


def environment(teardown: dict, name: str) -> dict:
    return next(item for item in teardown["environments"] if item["environment"] == name)


def torn_down(client, settings, session_factory, name="dev", headers=SAM) -> dict:
    teardown = request(client, environments=(name,)).json()
    decide(client, teardown["id"], name, headers=headers)
    drain(settings, session_factory)
    return get(client, teardown["id"])


def operations(settings) -> list[str]:
    return [f"{item['operation']} {item['region']}" for item in aws(settings).operations()]


# ---- preview ----

def test_preview_describes_what_an_environment_teardown_removes(client, provisioned):
    [dev] = preview(client).json()["environments"]
    assert (dev["environment"], dev["account_id"], dev["regions"], dev["approver_role"], dev["stacks"]) == (
        "dev", DEV_ACCOUNT, ["us-east-1"], "reviewer", ["invoice-ingest", "cloudinfra-bootstrap-invoice-ingest"])


def test_preview_lists_the_data_stores_that_are_backed_up(client, provisioned):
    [dev] = preview(client).json()["environments"]
    assert dev["data_stores"] == [{"service_id": "uploads", "resource_type": "AWS::S3::Bucket",
                                   "physical_name": f"invoice-ingest--uploads-{DEV_ACCOUNT}-us-east-1",
                                   "region": "us-east-1", "retained": True}]


def test_preview_lists_what_is_not_backed_up(client, provisioned):
    [dev] = preview(client).json()["environments"]
    assert dev["not_backed_up"] == [
        "processor (lambda.function): rebuilt from the template and the application repository",
        "CloudWatch Logs: not supported by AWS Backup"]


def test_preview_names_the_backup_account_and_retention(client, provisioned):
    body = preview(client).json()
    assert (body["backup_account"], body["retention_days"], body["blockers"]) == (BACKUP_ACCOUNT, 60, [])


def test_staging_and_production_need_a_platform_admin(client, provisioned):
    roles = [item["approver_role"] for item in preview(client, "project").json()["environments"]]
    assert roles == ["reviewer", "reviewer", "platform-admin", "platform-admin"]


def test_decommission_covers_every_environment_in_pipeline_order(client, provisioned):
    names = [item["environment"] for item in preview(client, "project", ()).json()["environments"]]
    assert names == ["dev", "test", "stage", "prod"]


@pytest.mark.parametrize("environments, message", [
    (("dev", "test"), "Choose exactly one environment to tear down."),
    (("sandbox",), "invoice-ingest has no environment 'sandbox'."),
])
def test_preview_rejects_invalid_environments(client, provisioned, environments, message):
    response = preview(client, environments=environments)
    assert (response.status_code, response.json()["detail"]) == (422, message)


def test_preview_of_unknown_project(client):
    assert client.post("/v1/projects/nope/teardowns:preview", json={"scope": "project"}).status_code == 404


def test_last_environment_must_be_decommissioned(client, settings, session_factory):
    client.post("/v1/projects", json=request_dict(environments=["dev"]), headers={"Idempotency-Key": "k1"})
    drain(settings, session_factory)
    assert preview(client).json()["blockers"] == [
        "dev is the project's last environment: decommission the project instead."]


def test_open_change_blocks_teardown(client, provisioned):
    read_back = client.get(f"{PROJECT}/repository:read-back").json()
    change = {**read_back["request"], "resources": [*read_back["request"]["resources"],
                                                    {"id": "jobs", "type": "sqs.queue", "config": {}}]}
    client.post(f"{PROJECT}/changes", json={"request": change, "base_commit": read_back["commit_sha"]})
    assert preview(client).json()["blockers"] == ["Change revision 2 is still open: merge or close it first."]


def test_release_in_progress_blocks_teardown_of_that_environment(client, provisioned):
    client.post(f"{PROJECT}/releases:simulate", json={"environment": "stage"}, headers=JORDAN)
    assert preview(client, environments=("stage",)).json()["blockers"] == [
        "A release to stage is in progress: finish or reject it first."]


def test_missing_backup_account_blocks_teardown(client, provisioned, session_factory, tmp_path):
    from fastapi.testclient import TestClient

    from app.api.application import ApplicationFactory

    plain = Settings(database_url=TEST_DATABASE_URL, local_state_dir=str(tmp_path), worker_poll_seconds=0)
    other = TestClient(ApplicationFactory(plain, session_factory=session_factory).create())
    body = other.post(f"{PROJECT}/teardowns:preview", json={"scope": "environment", "environments": ["dev"]}).json()
    assert (body["backup_account"], body["blockers"]) == (None, [
        "No central Backup account is configured: add a Backup account to the landing zone first."])


def test_data_store_without_a_name_blocks_teardown(client, settings, session_factory):
    payload = request_dict(resources=[{"id": "share", "type": "AWS::EFS::FileSystem", "config": {}}], connections=[])
    client.post("/v1/projects", json=payload, headers={"Idempotency-Key": "k1"})
    drain(settings, session_factory)
    assert preview(client).json()["blockers"] == [
        "Cannot back up share (AWS::EFS::FileSystem): its physical name is not in the template."]


# ---- request ----

def test_request_waits_for_one_approval_per_environment(client, provisioned):
    response = request(client, "project", ())
    body = response.json()
    assert (response.status_code, body["state"], body["requested_by"], body["scope"],
            [(item["environment"], item["state"]) for item in body["environments"]]) == (
        201, "in_progress", "jordan", "project",
        [("dev", "pending_approval"), ("test", "pending_approval"), ("stage", "pending_approval"),
         ("prod", "pending_approval")])


def test_request_needs_the_typed_project_name(client, provisioned):
    response = request(client, confirmation="invoice")
    assert (response.status_code, response.json()["detail"]) == (422, "Type the project name to confirm.")


def test_request_is_refused_while_blocked(client, provisioned):
    request(client)
    response = request(client, environments=("test",))
    assert (response.status_code, response.json()["detail"].startswith("A teardown of invoice-ingest is in progress")) == (
        409, True)


def test_nothing_happens_before_approval(client, settings, session_factory, provisioned):
    request(client)
    drain(settings, session_factory)
    assert (backup(settings).recovery_points(), aws(settings).operations()) == ([], [])


def test_open_teardown_blocks_changes(client, provisioned):
    request(client)
    read_back = client.get(f"{PROJECT}/repository:read-back").json()
    change = {**read_back["request"], "resources": [*read_back["request"]["resources"],
                                                    {"id": "jobs", "type": "sqs.queue", "config": {}}]}
    response = client.post(f"{PROJECT}/changes", json={"request": change, "base_commit": read_back["commit_sha"]})
    assert (response.status_code, response.json()["detail"].startswith("A teardown of invoice-ingest is in progress")) == (
        409, True)


# ---- approvals ----

def test_requester_cannot_approve(client, provisioned):
    teardown = request(client, headers=SAM).json()
    response = decide(client, teardown["id"], "dev", headers=SAM)
    assert (response.status_code, response.json()["detail"]) == (
        403, "You requested this teardown, so you cannot decide on it.")


def test_reviewers_cannot_approve_staging(client, provisioned):
    teardown = request(client, environments=("stage",)).json()
    response = decide(client, teardown["id"], "stage", headers=SAM)
    assert (response.status_code, response.json()["detail"]) == (
        403, "Only a platform admin can approve tearing down stage.")


def test_developers_cannot_approve(client, provisioned):
    teardown = request(client).json()
    assert decide(client, teardown["id"], "dev", headers={"X-Actor": "kim", "X-Roles": "developer"}).status_code == 403


def test_an_environment_is_decided_once(client, provisioned):
    teardown = request(client).json()
    decide(client, teardown["id"], "dev")
    response = decide(client, teardown["id"], "dev")
    assert (response.status_code, response.json()["detail"]) == (409, "dev is queued, not pending_approval.")


def test_approval_records_who_and_why(client, provisioned):
    teardown = request(client).json()
    dev = environment(decide(client, teardown["id"], "dev").json(), "dev")
    assert (dev["state"], dev["decided_by"], dev["decision_comment"]) == ("queued", "sam", "ok")


def test_unknown_environment_in_a_teardown(client, provisioned):
    teardown = request(client).json()
    assert decide(client, teardown["id"], "prod").status_code == 404


# ---- the teardown job ----

def test_approved_environment_is_torn_down(client, settings, session_factory, provisioned):
    dev = environment(torn_down(client, settings, session_factory), "dev")
    assert (dev["state"], dev["revision"], dev["error"]) == ("completed", 2, None)


def test_backups_are_locked_for_sixty_days(client, settings, session_factory, provisioned):
    [point] = environment(torn_down(client, settings, session_factory), "dev")["recovery_points"]
    completed = datetime.fromisoformat(point["completed_at"])
    assert (point["service_id"], point["vault"], point["account_id"],
            datetime.fromisoformat(point["locked_until"]) - completed) == (
        "uploads", "cloudinfra-teardown-us-east-1", BACKUP_ACCOUNT, timedelta(days=60))


def test_backup_comes_before_any_deletion(client, settings, session_factory, provisioned):
    torn_down(client, settings, session_factory)
    [point] = backup(settings).recovery_points()
    first_delete = datetime.fromisoformat(aws(settings).operations()[0]["at"])
    assert point.completed_at <= first_delete


def test_stacks_and_retained_data_are_deleted(client, settings, session_factory, provisioned):
    torn_down(client, settings, session_factory)
    assert operations(settings) == ["allow_stack_deletion us-east-1", "delete_stack us-east-1",
                                    "delete_data_store us-east-1"]


def test_bootstrap_stack_and_github_environment_are_removed(client, settings, session_factory, provisioned):
    torn_down(client, settings, session_factory)
    with pytest.raises(KeyError):
        github(settings).environment(OWNER, REPOSITORY, "dev")
    assert ([stack["environment"] for stack in aws(settings).stacks()],
            github(settings).repository_variables(OWNER, REPOSITORY)["ENVIRONMENT_ORDER"]) == (
        ["test", "stage", "prod"], "test,stage,prod")


def test_repository_is_committed_at_the_next_revision_without_the_environment(client, settings, session_factory,
                                                                              provisioned):
    teardown = torn_down(client, settings, session_factory)
    files = github(settings).read_files(OWNER, REPOSITORY).files
    record = json.loads(files[f"teardowns/{teardown['id']}.json"])
    assert ("config/dev.json" in files, json.loads(files["infra.json"])["environments"],
            record["environments"][0]["recovery_points"][0]["service_id"]) == (False, ["test", "stage", "prod"], "uploads")


def test_read_back_is_verified_after_the_teardown(client, settings, session_factory, provisioned):
    torn_down(client, settings, session_factory)
    read_back = client.get(f"{PROJECT}/repository:read-back").json()
    assert (read_back["verified"], read_back["findings"], read_back["design"]["revision"]) == (True, [], 2)


def test_environment_teardown_completes_the_request(client, settings, session_factory, provisioned):
    assert torn_down(client, settings, session_factory)["state"] == "completed"


def test_failed_backup_stops_before_anything_is_deleted(client, settings, session_factory, provisioned):
    backup(settings).fail_backups_of(f"arn:aws:s3:::invoice-ingest--uploads-{DEV_ACCOUNT}-us-east-1")
    dev = environment(torn_down(client, settings, session_factory), "dev")
    assert (dev["state"], dev["error"].startswith("Backup of"), aws(settings).operations()) == (
        "failed_needs_attention", True, [])


def test_unlocked_vault_stops_before_any_backup(client, settings, session_factory, provisioned):
    backup(settings).set_vault_lock("us-east-1", locked=False, min_retention_days=0)
    dev = environment(torn_down(client, settings, session_factory), "dev")
    assert (dev["state"], dev["error"], backup(settings).recovery_points(), aws(settings).operations()) == (
        "failed_needs_attention",
        "The central vault cloudinfra-teardown-us-east-1 is not locked for at least 60 days.", [], [])


def test_retry_resumes_without_repeating_finished_steps(client, settings, session_factory, provisioned):
    backup(settings).set_vault_lock("us-east-1", locked=False, min_retention_days=0)
    teardown = torn_down(client, settings, session_factory)
    backup(settings).set_vault_lock("us-east-1", locked=True, min_retention_days=60)
    decide(client, teardown["id"], "dev", "retry")
    drain(settings, session_factory)
    assert (environment(get(client, teardown["id"]), "dev")["state"], len(backup(settings).recovery_points())) == (
        "completed", 1)


def test_only_failed_environments_can_be_retried(client, provisioned):
    teardown = request(client).json()
    response = decide(client, teardown["id"], "dev", "retry")
    assert (response.status_code, response.json()["detail"]) == (409, "dev is pending_approval, not failed_needs_attention.")


def test_rejection_leaves_the_environment(client, settings, session_factory, provisioned):
    teardown = request(client).json()
    decided = decide(client, teardown["id"], "dev", "reject").json()
    drain(settings, session_factory)
    assert (decided["state"], environment(decided, "dev")["state"], aws(settings).operations()) == (
        "rejected", "rejected", [])


# ---- decommission ----

def test_staging_and_production_wait_for_the_other_environments(client, settings, session_factory, provisioned):
    teardown = request(client, "project", ()).json()
    decide(client, teardown["id"], "stage", headers=ALEX)
    decide(client, teardown["id"], "prod", headers=ALEX)
    drain(settings, session_factory)
    assert [(item["environment"], item["state"]) for item in get(client, teardown["id"])["environments"]] == [
        ("dev", "pending_approval"), ("test", "pending_approval"), ("stage", "approved"), ("prod", "approved")]


def decommissioned(client, settings, session_factory) -> dict:
    teardown = request(client, "project", ()).json()
    for name, headers in (("dev", SAM), ("test", SAM), ("stage", ALEX), ("prod", ALEX)):
        decide(client, teardown["id"], name, headers=headers)
    drain(settings, session_factory)
    return get(client, teardown["id"])


def test_decommission_tears_down_production_last(client, settings, session_factory, provisioned):
    decommissioned(client, settings, session_factory)
    deleted = [item["account"] for item in aws(settings).operations() if item["operation"] == "delete_stack"]
    assert deleted == [DEV_ACCOUNT, "333333333333", "444444444444", "555555555555"]


def test_decommission_archives_the_repository_and_marks_the_project(client, settings, session_factory, provisioned):
    teardown = decommissioned(client, settings, session_factory)
    [project] = client.get("/v1/projects").json()
    assert (teardown["state"], project["status"], github(settings).is_archived(OWNER, REPOSITORY),
            github(settings).repository_properties(OWNER, REPOSITORY)["cloudinfra-state"]) == (
        "completed", "decommissioned", True, "decommissioned")


def test_decommissioned_repository_says_so_and_keeps_the_last_design(client, settings, session_factory, provisioned):
    decommissioned(client, settings, session_factory)
    files = github(settings).read_files(OWNER, REPOSITORY).files
    assert ("decommissioned" in files["README.md"], json.loads(files["infra.json"])["environments"]) == (True, ["prod"])


def test_rejecting_one_environment_stops_the_rest(client, settings, session_factory, provisioned):
    teardown = request(client, "project", ()).json()
    decide(client, teardown["id"], "dev")
    drain(settings, session_factory)
    decide(client, teardown["id"], "test", "reject")
    result = get(client, teardown["id"])
    [project] = client.get("/v1/projects").json()
    assert ([(item["environment"], item["state"]) for item in result["environments"]], result["state"],
            project["status"], project["environments"]) == (
        [("dev", "completed"), ("test", "rejected"), ("stage", "cancelled"), ("prod", "cancelled")],
        "partially_completed", "active", ["test", "stage", "prod"])


# ---- restore ----

def restore(client, teardown_id, decision="restore", headers=JORDAN):
    return client.post(f"{PROJECT}/teardowns/{teardown_id}:{decision}", json={"comment": "ok"}, headers=headers)


def test_restore_rebuilds_an_environment_from_its_backups(client, settings, session_factory, provisioned):
    teardown = torn_down(client, settings, session_factory)
    restore(client, teardown["id"])
    restore(client, teardown["id"], "approve-restore", headers=SAM)
    drain(settings, session_factory)
    [restored] = backup(settings).restores()
    assert ((restored["account"], restored["physical_name"]), get(client, teardown["id"])["restore"]["state"],
            "import_stack us-east-1" in operations(settings),
            github(settings).environment(OWNER, REPOSITORY, "dev")["AWS_ACCOUNT_ID"]) == (
        (DEV_ACCOUNT, f"invoice-ingest--uploads-{DEV_ACCOUNT}-us-east-1"), "restored", True, DEV_ACCOUNT)


def test_restore_commits_the_environment_back(client, settings, session_factory, provisioned):
    teardown = torn_down(client, settings, session_factory)
    restore(client, teardown["id"])
    restore(client, teardown["id"], "approve-restore", headers=SAM)
    drain(settings, session_factory)
    read_back = client.get(f"{PROJECT}/repository:read-back").json()
    assert (read_back["verified"], read_back["design"]["revision"], read_back["request"]["environments"]) == (
        True, 3, ["dev", "test", "stage", "prod"])


def test_restore_of_a_decommissioned_project_reactivates_it(client, settings, session_factory, provisioned):
    teardown = decommissioned(client, settings, session_factory)
    restore(client, teardown["id"])
    restore(client, teardown["id"], "approve-restore", headers=ALEX)
    drain(settings, session_factory)
    [project] = client.get("/v1/projects").json()
    assert (project["status"], project["environments"], github(settings).is_archived(OWNER, REPOSITORY),
            len(backup(settings).restores())) == ("active", ["dev", "test", "stage", "prod"], False, 4)


def test_restore_needs_a_platform_admin_when_staging_or_production_come_back(client, settings, session_factory,
                                                                            provisioned):
    teardown = decommissioned(client, settings, session_factory)
    restore(client, teardown["id"])
    response = restore(client, teardown["id"], "approve-restore", headers=SAM)
    assert (response.status_code, response.json()["detail"]) == (403, "Only a platform admin can approve this restore.")


def test_restore_cannot_be_approved_by_its_requester(client, settings, session_factory, provisioned):
    teardown = torn_down(client, settings, session_factory)
    restore(client, teardown["id"], headers=SAM)
    assert restore(client, teardown["id"], "approve-restore", headers=SAM).status_code == 403


def test_restore_can_be_rejected(client, settings, session_factory, provisioned):
    teardown = torn_down(client, settings, session_factory)
    restore(client, teardown["id"])
    assert restore(client, teardown["id"], "reject-restore", headers=SAM).json()["restore"]["state"] == "rejected"


def test_restore_is_requested_once(client, settings, session_factory, provisioned):
    teardown = torn_down(client, settings, session_factory)
    restore(client, teardown["id"])
    response = restore(client, teardown["id"])
    assert (response.status_code, response.json()["detail"]) == (409, "A restore of this teardown is already requested.")


def test_restore_needs_a_completed_teardown(client, provisioned):
    teardown = request(client).json()
    assert restore(client, teardown["id"]).status_code == 409


def test_restore_is_refused_when_a_super_user_deleted_a_backup(client, settings, session_factory, provisioned):
    teardown = torn_down(client, settings, session_factory)
    [point] = environment(teardown, "dev")["recovery_points"]
    later = datetime.now(UTC) + timedelta(days=61)
    backup(settings).delete_recovery_point(point["recovery_point_ref"], role="CloudInfraBackupSuperUser", at=later)
    response = restore(client, teardown["id"])
    assert (response.status_code, response.json()["detail"]) == (
        409, "The backup of uploads in dev (us-east-1) no longer exists, so it cannot be restored.")


def test_restore_approval_needs_a_request(client, settings, session_factory, provisioned):
    teardown = torn_down(client, settings, session_factory)
    assert restore(client, teardown["id"], "approve-restore", headers=SAM).status_code == 409


# ---- listing ----

def test_all_teardowns_newest_first(client, settings, session_factory, provisioned):
    first = torn_down(client, settings, session_factory)
    second = request(client, environments=("test",)).json()
    assert [item["id"] for item in client.get("/v1/teardowns").json()] == [second["id"], first["id"]]


def test_project_teardowns(client, provisioned):
    teardown = request(client).json()
    assert [item["id"] for item in client.get(f"{PROJECT}/teardowns").json()] == [teardown["id"]]


def test_unknown_teardown(client, provisioned):
    assert client.get(f"{PROJECT}/teardowns/00000000-0000-0000-0000-000000000000").status_code == 404


def test_projects_list_their_environments(client, provisioned):
    assert client.get("/v1/projects").json()[0]["environments"] == ["dev", "test", "stage", "prod"]


def test_retry_after_a_failed_backup_skips_the_vault_check_it_passed(client, settings, session_factory, provisioned):
    backup(settings).fail_backups_of(f"arn:aws:s3:::invoice-ingest--uploads-{DEV_ACCOUNT}-us-east-1")
    teardown = torn_down(client, settings, session_factory)
    backup(settings).clear_failures()
    decide(client, teardown["id"], "dev", "retry")
    drain(settings, session_factory)
    job = client.get(f"/v1/jobs/{environment(get(client, teardown['id']), 'dev')['job_id']}").json()
    assert ([step["name"] for step in job["steps"]][:2], environment(get(client, teardown["id"]), "dev")["state"]) == (
        ["backup:us-east-1:uploads", "verify-backups"], "completed")


def test_nothing_is_deleted_without_a_locked_backup_in_the_vault(client, settings, session_factory, provisioned,
                                                                 monkeypatch):
    monkeypatch.setattr(LocalBackup, "recovery_point", lambda self, arn: None)
    dev = environment(torn_down(client, settings, session_factory), "dev")
    assert (dev["state"], dev["error"], aws(settings).operations()) == (
        "failed_needs_attention", "No locked backup in the central vault for uploads (us-east-1); nothing was deleted.",
        [])


def test_decommissioned_projects_cannot_be_torn_down_again(client, settings, session_factory, provisioned):
    decommissioned(client, settings, session_factory)
    assert preview(client, "project", ()).json()["blockers"] == [
        "Project 'invoice-ingest' is decommissioned; only active projects can be torn down."]


def test_a_restored_teardown_cannot_be_restored_again(client, settings, session_factory, provisioned):
    teardown = torn_down(client, settings, session_factory)
    restore(client, teardown["id"])
    restore(client, teardown["id"], "approve-restore", headers=SAM)
    drain(settings, session_factory)
    response = restore(client, teardown["id"])
    assert (response.status_code, response.json()["detail"]) == (409, "This teardown was already restored.")


def test_restore_refuses_an_environment_that_was_added_back(client, settings, session_factory, provisioned):
    teardown = torn_down(client, settings, session_factory)
    read_back = client.get(f"{PROJECT}/repository:read-back").json()
    request_with_dev = {**read_back["request"], "environments": [*read_back["request"]["environments"], "dev"]}
    change = client.post(f"{PROJECT}/changes", json={"request": request_with_dev,
                                                     "base_commit": read_back["commit_sha"]}).json()
    drain(settings, session_factory)
    client.post(f"{PROJECT}/changes/{change['id']}:merge")
    response = restore(client, teardown["id"])
    assert (response.status_code, response.json()["detail"]) == (
        409, "dev exists in the project again, so it cannot be restored over.")


def test_restore_fails_when_a_backup_disappears_before_it_runs(client, settings, session_factory, provisioned):
    teardown = torn_down(client, settings, session_factory)
    restore(client, teardown["id"])
    [point] = environment(teardown, "dev")["recovery_points"]
    backup(settings).delete_recovery_point(point["recovery_point_ref"], role="CloudInfraBackupSuperUser",
                                           at=datetime.now(UTC) + timedelta(days=61))
    restore(client, teardown["id"], "approve-restore", headers=SAM)
    drain(settings, session_factory)
    assert get(client, teardown["id"])["restore"]["state"] == "failed"


def test_teardowns_record_the_provider(client, provisioned):
    assert request(client).json()["provider"] == "aws"
