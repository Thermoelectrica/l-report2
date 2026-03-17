"""Application configuration management."""

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).parent.parent / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application
    app_env: Literal["development", "production"] = "development"
    log_level: str = "INFO"

    # Report Repository
    reports_path: str

    # Data Database
    data_db_host: str
    data_db_port: int = 5432
    data_db_name: str
    data_db_user: str
    data_db_password: str

    # Metadata Database
    meta_db_host: str
    meta_db_port: int = 5432
    meta_db_name: str
    meta_db_user: str
    meta_db_password: str

    # Storage
    storage_backend: Literal["filesystem", "s3"] = "filesystem"
    storage_path: str = "uploaded_files"
    s3_bucket: str | None = None
    s3_endpoint: str | None = None
    s3_access_key: str | None = None
    s3_secret_key: str | None = None

    # S3 Image Storage (for images referenced in reports)
    s3_images_bucket: str | None = None
    s3_images_endpoint: str | None = None
    s3_images_access_key: str | None = None
    s3_images_secret_key: str | None = None
    s3_images_region: str | None = None
    presigned_url_expiration: int = 3600  # 1 hour in seconds

    # Task Queue
    task_queue_backend: Literal["background_tasks", "celery"] = "background_tasks"
    celery_broker_url: str | None = None

    # Defaults
    default_query_timeout: int = 300
    max_pdf_size_mb: int = 50
    cache_ttl_minutes: int = 5

    @property
    def data_db_url(self) -> str:
        """Get async PostgreSQL connection URL for data database."""
        return (
            f"postgresql+asyncpg://{self.data_db_user}:{self.data_db_password}"
            f"@{self.data_db_host}:{self.data_db_port}/{self.data_db_name}"
        )

    @property
    def meta_db_url(self) -> str:
        """Get async PostgreSQL connection URL for metadata database."""
        return (
            f"postgresql+asyncpg://{self.meta_db_user}:{self.meta_db_password}"
            f"@{self.meta_db_host}:{self.meta_db_port}/{self.meta_db_name}"
        )

    @property
    def meta_db_url_sync(self) -> str:
        """Get sync PostgreSQL connection URL for Alembic migrations."""
        return (
            f"postgresql://{self.meta_db_user}:{self.meta_db_password}"
            f"@{self.meta_db_host}:{self.meta_db_port}/{self.meta_db_name}"
        )


settings = Settings()
