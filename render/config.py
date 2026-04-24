"""Application configuration management."""

from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).parent.parent / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore extra fields (like auth settings)
    )

    # Application
    app_env: Literal["development", "production"] = "development"
    log_level: str = "INFO"

    # Report Repository
    reports_path: str

    # Data Database
    data_db_url: str
    data_db_password: str

    # Metadata Database
    meta_db_url: str
    meta_db_password: str

    # Parsed Data Database components (for backward compatibility)
    @property
    def data_db_host(self) -> str:
        """Extract host from data database URL."""
        parsed = urlparse(self.data_db_url)
        return parsed.hostname or "localhost"

    @property
    def data_db_port(self) -> int:
        """Extract port from data database URL."""
        parsed = urlparse(self.data_db_url)
        return parsed.port or 5432

    @property
    def data_db_name(self) -> str:
        """Extract database name from data database URL."""
        parsed = urlparse(self.data_db_url)
        return parsed.path.lstrip("/") if parsed.path else ""

    @property
    def data_db_user(self) -> str:
        """Extract username from data database URL."""
        parsed = urlparse(self.data_db_url)
        return parsed.username or ""

    # Parsed Metadata Database components (for backward compatibility)
    @property
    def meta_db_host(self) -> str:
        """Extract host from metadata database URL."""
        parsed = urlparse(self.meta_db_url)
        return parsed.hostname or "localhost"

    @property
    def meta_db_port(self) -> int:
        """Extract port from metadata database URL."""
        parsed = urlparse(self.meta_db_url)
        return parsed.port or 5432

    @property
    def meta_db_name(self) -> str:
        """Extract database name from metadata database URL."""
        parsed = urlparse(self.meta_db_url)
        return parsed.path.lstrip("/") if parsed.path else ""

    @property
    def meta_db_user(self) -> str:
        """Extract username from metadata database URL."""
        parsed = urlparse(self.meta_db_url)
        return parsed.username or ""

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

    def get_data_db_url_with_password(self) -> str:
        """Get async PostgreSQL connection URL for data database with password."""
        parsed = urlparse(self.data_db_url)
        # Reconstruct URL with password
        netloc = f"{parsed.username}:{self.data_db_password}@{parsed.hostname}"
        if parsed.port:
            netloc += f":{parsed.port}"
        return f"{parsed.scheme}://{netloc}{parsed.path}"

    def get_meta_db_url_with_password(self) -> str:
        """Get async PostgreSQL connection URL for metadata database with password."""
        parsed = urlparse(self.meta_db_url)
        # Reconstruct URL with password
        netloc = f"{parsed.username}:{self.meta_db_password}@{parsed.hostname}"
        if parsed.port:
            netloc += f":{parsed.port}"
        return f"{parsed.scheme}://{netloc}{parsed.path}"

    @property
    def meta_db_url_sync(self) -> str:
        """Get sync PostgreSQL connection URL for Alembic migrations."""
        parsed = urlparse(self.meta_db_url)
        # Convert to sync driver and add password
        netloc = f"{parsed.username}:{self.meta_db_password}@{parsed.hostname}"
        if parsed.port:
            netloc += f":{parsed.port}"
        # Replace asyncpg with psycopg2 for sync
        scheme = parsed.scheme.replace("+asyncpg", "")
        return f"{scheme}://{netloc}{parsed.path}"


settings = Settings()
