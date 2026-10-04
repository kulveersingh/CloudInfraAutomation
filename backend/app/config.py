from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Runtime configuration, read from environment variables (ECS task definitions set them)."""

    database_url: str = "postgresql+psycopg://cloudinfra:cloudinfra@localhost:5432/cloudinfra"
    github_mode: str = "local"
    aws_mode: str = "local"
    local_state_dir: str = "var"
    github_owner: str = "acme-platform"
    worker_poll_seconds: float = 2.0
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:8080"]
