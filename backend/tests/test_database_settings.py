from app.config import Settings


def test_full_url_is_used_when_no_password_is_injected():
    settings = Settings(database_url="postgresql+psycopg://u:p@localhost:5432/x")
    assert settings.sqlalchemy_url() == "postgresql+psycopg://u:p@localhost:5432/x"


def test_url_is_built_from_parts_when_aurora_password_is_injected():
    settings = Settings(database_host="db.cluster.local", database_name="cloudinfra", database_user="admin",
                        database_password="p@ss/word")
    assert settings.sqlalchemy_url() == "postgresql+psycopg://admin:p%40ss%2Fword@db.cluster.local:5432/cloudinfra"


def test_port_can_be_set():
    settings = Settings(database_host="db", database_port=6543, database_password="x")
    assert ":6543/" in settings.sqlalchemy_url()
