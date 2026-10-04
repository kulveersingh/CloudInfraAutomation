import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from app.db import models
from app.db.database import Database
from app.seed import ReferenceDataSeeder, SeedCommand
from tests.factories import TEST_DATABASE_URL


def count(session, model) -> int:
    return session.scalar(select(func.count()).select_from(model))


def reference_counts(session) -> tuple:
    return tuple(count(session, model) for model in (
        models.Portfolio, models.Product, models.Environment, models.Region, models.AccountBinding))


def test_seed_inserts_reference_data(seeded):
    assert reference_counts(seeded) == (3, 5, 5, 6, 15)


def test_seed_sets_organization_default(seeded):
    assert seeded.get(models.OrganizationSettings, 1).default_cost_center == "CC-1000"


def test_seed_is_idempotent(seeded):
    ReferenceDataSeeder(seeded).seed()
    assert reference_counts(seeded) == (3, 5, 5, 6, 15)


def test_account_belongs_to_one_environment_only(seeded):
    seeded.add(models.AccountBinding(environment_id="dev", portfolio_id="pf-retail", account_id="555555555555"))
    with pytest.raises(IntegrityError):
        seeded.flush()


def test_database_provides_working_sessions():
    with Database(TEST_DATABASE_URL).session_factory() as session:
        assert session.execute(text("SELECT 1")).scalar() == 1


def test_seed_command_uses_configured_database(settings, session):
    SeedCommand(settings).run()
    assert count(session, models.Portfolio) == 3
