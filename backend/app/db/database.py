from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


class Database:
    """Engine and session factory for one database URL (Aurora PostgreSQL on AWS, PostgreSQL locally)."""

    def __init__(self, url: str):
        self.engine = create_engine(url, pool_pre_ping=True)
        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)
