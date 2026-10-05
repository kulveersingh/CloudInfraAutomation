"""The landing zone's neutral core (§22.10.3, MC-3a): provider answers, one landing zone per cloud, neutral words."""

from pathlib import Path

import pytest

from app.db import models
from app.landing_zone.repository import LandingZoneRepository
from tests.lz_factories import answers_dict
from tests.test_lz_api import ALEX, BASE, approve, create, propose, submitted

CORE = Path(__file__).parents[1] / "app" / "landing_zone"


# ---- provider answers through the API ----

def test_an_invalid_management_email_is_refused(client):
    response = propose(client, management_email="not-an-email")
    assert (response.status_code, "management_email" in response.json()["detail"]) == (422, True)


def test_provider_answers_are_sent_on_their_own(client):
    body = {"provider": "aws", "edits": [], "answers": {
        **{key: value for key, value in answers_dict().items() if key != "management_email"},
        "provider_answers": {"management_email": "aws@acme.example"}}}
    assert client.post(f"{BASE}:propose", json=body, headers=ALEX).json()["problems"] == []


def test_stored_designs_answer_in_the_neutral_shape(client):
    design = create(client).json()
    assert (design["answers"]["provider_answers"], "management_email" in design["answers"]) == (
        {"management_email": "aws-management@acme.example"}, False)


def test_ous_say_which_service_created_them(client):
    security = next(ou for ou in propose(client).json()["ous"] if ou["key"] == "security")
    assert (security["created_by_service"], "created_by_control_tower" in security) == (True, False)


# ---- one landing zone per cloud ----

def record(session, provider: str, version: int, status: str = "applied") -> models.LandingZoneDesignRecord:
    item = models.LandingZoneDesignRecord(version=version, provider=provider, answers=answers_dict(), edits=[],
                                          status=status, created_by="alex")
    session.add(item)
    session.commit()
    return item


def test_versions_count_per_cloud(session):
    record(session, "aws", 1)
    record(session, "gcp", 1)
    repository = LandingZoneRepository(session)
    assert (repository.next_version("aws"), repository.next_version("gcp"), repository.next_version("azure")) == (2, 2, 1)


def test_the_latest_applied_design_is_per_cloud(session):
    record(session, "aws", 1)
    gcp = record(session, "gcp", 1)
    record(session, "gcp", 2, status="draft")
    assert LandingZoneRepository(session).latest_applied("gcp").id == gcp.id


def test_designs_can_be_listed_per_cloud(client, session):
    create(client)
    record(session, "gcp", 1, status="draft")
    providers = [design["provider"] for design in client.get(f"{BASE}/designs", params={"provider": "aws"},
                                                             headers=ALEX).json()]
    assert providers == ["aws"]


def test_read_back_takes_the_cloud(client):
    approve(client, submitted(client))
    response = client.get(f"{BASE}/repository:read-back", params={"provider": "aws"}, headers=ALEX)
    assert (response.status_code, response.json()["verified"]) == (200, True)


def test_a_cloud_without_an_applied_landing_zone_has_nothing_to_read_back(client):
    approve(client, submitted(client))
    response = client.get(f"{BASE}/repository:read-back", params={"provider": "gcp"}, headers=ALEX)
    assert response.status_code == 404


def test_the_aws_backup_account_comes_from_the_aws_landing_zone_only(session):
    from app.teardown.backup_account import BackupAccountResolver

    gcp = record(session, "gcp", 1)
    gcp.accounts = {"acme-backup": "123456789012"}
    session.commit()
    assert BackupAccountResolver({}, LandingZoneRepository(session)).resolve("aws") is None


# ---- the core holds no cloud's words ----

@pytest.mark.parametrize("word", ["management_email", "created_by_control_tower", "Control Tower", "CloudFormation"])
def test_the_landing_zone_core_names_no_cloud_specifics(word):
    found = [str(path.relative_to(CORE)) for path in CORE.rglob("*") if path.suffix in (".py", ".yaml")
             and word in path.read_text()]
    assert found == []
