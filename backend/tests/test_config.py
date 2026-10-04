from app.config import Settings


def test_defaults_use_local_adapters():
    settings = Settings()
    assert (settings.github_mode, settings.aws_mode) == ("local", "local")


def test_database_url_is_read_from_environment(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@db:5432/x")
    assert Settings().database_url == "postgresql+psycopg://u:p@db:5432/x"


def test_default_github_owner():
    assert Settings().github_owner == "acme-platform"
