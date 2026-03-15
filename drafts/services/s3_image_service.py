"""S3 image service for generating presigned URLs."""

import logging
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from config import settings

logger = logging.getLogger(__name__)


class S3ImageService:
    """Service for handling S3-stored images in reports."""

    def __init__(self):
        """Initialize S3 client for images if configured."""
        self.enabled = False
        self.s3_client = None
        self.bucket = None
        self.expiration = settings.presigned_url_expiration

        # Check if S3 image storage is configured
        if all(
            [
                settings.s3_images_bucket,
                settings.s3_images_endpoint,
                settings.s3_images_access_key,
                settings.s3_images_secret_key,
            ]
        ):
            try:
                self.s3_client = boto3.client(
                    "s3",
                    endpoint_url=settings.s3_images_endpoint,
                    aws_access_key_id=settings.s3_images_access_key,
                    aws_secret_access_key=settings.s3_images_secret_key,
                    region_name=settings.s3_images_region or "us-east-1",
                )
                self.bucket = settings.s3_images_bucket
                self.enabled = True
                logger.info(f"S3 image service initialized with bucket: {self.bucket}")
            except Exception as e:
                logger.warning(f"Failed to initialize S3 image service: {e}")
                self.enabled = False
        else:
            logger.info(
                "S3 image service not configured - image URLs will be returned as-is"
            )

    def generate_presigned_url(
        self, image_path: str, expiration: Optional[int] = None
    ) -> str:
        """
        Generate a presigned URL for an S3 image.

        Args:
            image_path: Path/key of the image in S3 bucket (e.g., "charts/chart1.png")
            expiration: URL expiration time in seconds (default: from settings)

        Returns:
            Presigned URL if S3 is configured, otherwise returns the original path
        """
        if not self.enabled or not image_path:
            return image_path

        # Remove leading slash if present
        image_path = image_path.lstrip("/")

        try:
            url = self.s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": image_path},
                ExpiresIn=expiration or self.expiration,
            )
            logger.debug(f"Generated presigned URL for: {image_path}")
            return url
        except ClientError as e:
            logger.error(f"Failed to generate presigned URL for {image_path}: {e}")
            # Return original path as fallback
            return image_path
        except Exception as e:
            logger.error(
                f"Unexpected error generating presigned URL for {image_path}: {e}"
            )
            return image_path

    def image_url(self, image_path: str) -> str:
        """
        Convenience method to generate image URL (alias for generate_presigned_url).

        This is the method that will be exposed as a Jinja2 filter.

        Args:
            image_path: Path/key of the image in S3 bucket

        Returns:
            Presigned URL or original path
        """
        return self.generate_presigned_url(image_path)

    def check_image_exists(self, image_path: str) -> bool:
        """
        Check if an image exists in S3.

        Args:
            image_path: Path/key of the image in S3 bucket

        Returns:
            True if image exists, False otherwise
        """
        if not self.enabled:
            return False

        image_path = image_path.lstrip("/")

        try:
            self.s3_client.head_object(Bucket=self.bucket, Key=image_path)
            return True
        except ClientError:
            return False


# Global S3 image service instance
s3_image_service = S3ImageService()
