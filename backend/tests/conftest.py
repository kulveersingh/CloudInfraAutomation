import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from tests.factories import TEST_DATABASE_URL


def _ensure_test_database() -> None:
    admin_url = TEST_DATABASE_URL.rsplit("/", 1)[0] + "/postgres"
    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        exists = connection.execute(
            text("SELECT 1 FROM pg_database WHERE datname = 'cloudinfra_test'")
        ).scalar()
        if not exists:
            connection.execute(text("CREATE DATABASE cloudinfra_test"))
    admin.dispose()


@pytest.fixture(scope="session")
def engine():
    from app.db.models import Base

    _ensure_test_database()
    test_engine = create_engine(TEST_DATABASE_URL)
    Base.metadata.drop_all(test_engine)
    Base.metadata.create_all(test_engine)
    yield test_engine
    test_engine.dispose()


@pytest.fixture
def session_factory(engine):
    from app.db.models import Base

    factory = sessionmaker(bind=engine, expire_on_commit=False)
    yield factory
    tables = ", ".join(table.name for table in Base.metadata.sorted_tables)
    with engine.begin() as connection:
        connection.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


@pytest.fixture
def session(session_factory):
    with session_factory() as db_session:
        yield db_session


@pytest.fixture
def seeded(session):
    from app.seed import ReferenceDataSeeder

    ReferenceDataSeeder(session).seed()
    return session


@pytest.fixture
def settings(tmp_path):
    from app.config import Settings

    return Settings(database_url=TEST_DATABASE_URL, local_state_dir=str(tmp_path), worker_poll_seconds=0)


@pytest.fixture
def client(session_factory, settings):
    from fastapi.testclient import TestClient

    from app.api.application import ApplicationFactory
    from app.seed import ReferenceDataSeeder

    with session_factory() as db_session:
        ReferenceDataSeeder(db_session).seed()
    app = ApplicationFactory(settings, session_factory=session_factory).create()
    return TestClient(app)


@pytest.fixture
def local_github(tmp_path):
    from app.adapters.local_github import LocalGitHub

    return LocalGitHub(tmp_path)


@pytest.fixture
def local_aws(tmp_path):
    from app.adapters.local_aws import LocalAws

    return LocalAws(tmp_path)
