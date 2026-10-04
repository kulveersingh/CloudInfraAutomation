import uuid
from types import SimpleNamespace

from app.releases.executor import LocalReleaseExecutor

RELEASE = SimpleNamespace(id=uuid.UUID(int=1), project_name="invoice-ingest", environment_id="stage",
                          commit_sha="4f78c64a1b2c")


def test_execution_succeeds(tmp_path):
    assert LocalReleaseExecutor(tmp_path).execute(RELEASE).succeeded is True


def test_execution_detail_names_the_change_set(tmp_path):
    assert "cs-4f78c64a1b2c" in LocalReleaseExecutor(tmp_path).execute(RELEASE).detail


def test_execution_is_recorded(tmp_path):
    executor = LocalReleaseExecutor(tmp_path)
    executor.execute(RELEASE)
    assert executor.history() == [{"release_id": str(RELEASE.id), "project": "invoice-ingest",
                                   "environment": "stage", "change_set": "cs-4f78c64a1b2c"}]


def test_history_starts_empty(tmp_path):
    assert LocalReleaseExecutor(tmp_path).history() == []
