from pydantic_settings import BaseSettings
from sqlalchemy.engine import URL

DRIVER = "postgresql+psycopg"


class Settings(BaseSettings):
    """Runtime configuration, read from environment variables (ECS task definitions set them).

    Locally DATABASE_URL is used as-is. On ECS the Aurora-managed secret injects DATABASE_PASSWORD and the
    task definition sets the host, so the URL is built from parts.
    """

    database_url: str = "postgresql+psycopg://cloudinfra:cloudinfra@localhost:5432/cloudinfra"
    database_host: str | None = None
    database_port: int = 5432
    database_name: str = "cloudinfra"
    database_user: str = "cloudinfra"
    database_password: str | None = None
    github_mode: str = "local"
    aws_mode: str = "local"
    local_state_dir: str = "var"
    github_owner: str = "acme-platform"
    # Keys that sign the manifest in every generated repository (§21.2). On AWS a Secrets Manager secret injects them;
    # the local key is fixed and not secret.
    manifest_signing_keys: dict[str, str] = {"local-dev": "local-development-key-not-secret"}
    manifest_active_key: str = "local-dev"
    worker_poll_seconds: float = 2.0
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:8080"]

    def sqlalchemy_url(self) -> str:
        if self.database_password is None:
            return self.database_url
        return URL.create(DRIVER, username=self.database_user, password=self.database_password,
                          host=self.database_host, port=self.database_port,
                          database=self.database_name).render_as_string(hide_password=False)
