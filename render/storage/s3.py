"""S3-compatible storage backend (Yandex Object Storage)."""

import logging

import boto3
from botocore.exceptions import ClientError

from ..config import settings
from .base import StorageBackend

logger = logging.getLogger(__name__)


class S3Storage(StorageBackend):
    """Store PDFs in S3-compatible object storage."""

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

    def _get_key(self, cache_key: str) -> str:
        """Get S3 object key for a cache key."""
        return f"renders/{cache_key}.pdf"

    async def save(self, cache_key: str, pdf_bytes: bytes) -> str:
        """Save PDF to S3."""
        key = self._get_key(cache_key)
        try:
            self.s3_client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=pdf_bytes,
                ContentType="application/pdf",
            )
            path = f"s3://{self.bucket}/{key}"
            logger.info(f"Saved PDF to S3: {path}")
            return path
        except ClientError as e:
            logger.error(f"Failed to save PDF to S3: {e}")
            raise

    async def retrieve(self, cache_key: str) -> bytes:
        """Retrieve PDF from S3."""
        key = self._get_key(cache_key)
        try:
            response = self.s3_client.get_object(Bucket=self.bucket, Key=key)
            return response["Body"].read()
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                raise FileNotFoundError(f"PDF not found: {cache_key}")
            logger.error(f"Failed to retrieve PDF from S3: {e}")
            raise

    async def exists(self, cache_key: str) -> bool:
        """Check if PDF exists in S3."""
        key = self._get_key(cache_key)
        try:
            self.s3_client.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError:
            return False

    async def delete(self, cache_key: str) -> None:
        """Delete PDF from S3."""
        key = self._get_key(cache_key)
        try:
            self.s3_client.delete_object(Bucket=self.bucket, Key=key)
            logger.info(f"Deleted PDF from S3: {key}")
        except ClientError as e:
            logger.error(f"Failed to delete PDF from S3: {e}")
            raise
