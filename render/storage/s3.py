"""S3-compatible storage backend (Yandex Object Storage)."""

import logging

import boto3
from botocore.exceptions import ClientError

from ..config import settings
from .base import StorageBackend

logger = logging.getLogger(__name__)


class S3Storage(StorageBackend):
    """Store output files in S3-compatible object storage."""

    def __init__(self):
        if not all(
            [
                settings.s3_bucket,
                settings.s3_endpoint,
                settings.s3_access_key,
                settings.s3_secret_key,
            ]
        ):
            raise ValueError("S3 storage requires bucket, endpoint, and credentials")

        self.s3_client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
        )
        self.bucket = settings.s3_bucket
        logger.info(f"S3 storage initialized with bucket: {self.bucket}")

    def _get_key(self, cache_key: str, file_extension: str = "pdf") -> str:
        """Get S3 object key for a cache key."""
        return f"renders/{cache_key}.{file_extension}"

    def _get_content_type(self, file_extension: str) -> str:
        """Get content type for file extension."""
        content_types = {
            "pdf": "application/pdf",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "html": "text/html",
        }
        return content_types.get(file_extension, "application/octet-stream")

    async def save(self, cache_key: str, pdf_bytes: bytes, file_extension: str = "pdf") -> str:
        """Save output file to S3."""
        key = self._get_key(cache_key, file_extension)
        content_type = self._get_content_type(file_extension)
        try:
            self.s3_client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=pdf_bytes,
                ContentType=content_type,
            )
            path = f"s3://{self.bucket}/{key}"
            logger.info(f"Saved file to S3: {path}")
            return path
        except ClientError as e:
            logger.error(f"Failed to save file to S3: {e}")
            raise

    async def retrieve(self, cache_key: str) -> bytes:
        """Retrieve file from S3 (tries common extensions)."""
        for ext in ["pdf", "docx", "html"]:
            key = self._get_key(cache_key, ext)
            try:
                response = self.s3_client.get_object(Bucket=self.bucket, Key=key)
                return response["Body"].read()
            except ClientError as e:
                if e.response["Error"]["Code"] != "NoSuchKey":
                    logger.error(f"Failed to retrieve file from S3: {e}")
                    raise
        raise FileNotFoundError(f"File not found: {cache_key}")

    async def exists(self, cache_key: str) -> bool:
        """Check if file exists in S3 (tries common extensions)."""
        for ext in ["pdf", "docx", "html"]:
            key = self._get_key(cache_key, ext)
            try:
                self.s3_client.head_object(Bucket=self.bucket, Key=key)
                return True
            except ClientError:
                continue
        return False

    async def delete(self, cache_key: str) -> None:
        """Delete file from S3 (tries common extensions)."""
        for ext in ["pdf", "docx", "html"]:
            key = self._get_key(cache_key, ext)
            try:
                self.s3_client.delete_object(Bucket=self.bucket, Key=key)
                logger.info(f"Deleted file from S3: {key}")
            except ClientError as e:
                logger.debug(f"Could not delete {key}: {e}")
