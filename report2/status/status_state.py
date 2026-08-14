"""Status page state management."""

import logging
from pathlib import Path
from typing import Dict, List

import reflex as rx

from render.config import settings
from report2.config import get_auth_config

logger = logging.getLogger(__name__)


class StatusState(rx.State):
    """State for the status page."""
    
    config_data: Dict[str, Dict[str, str]] = {}
    config_error: str = ""
    
    report_names: List[str] = []
    reports_error: str = ""
    
    @rx.event
    async def on_load(self):
        """Load status information when page loads."""
        await self.load_config()
        await self.load_reports_structure()
    
    @rx.event
    async def load_config(self):
        """Load all configuration variables."""
        try:
            auth_config = get_auth_config()
            
            # Collect all config data
            config = {
                "Application": {
                    "app_env": settings.app_env,
                    "log_level": settings.log_level,
                },
                "Reports": {
                    "reports_path": settings.reports_path,
                },
                "Data Database": {
                    "data_db_url": self._mask_password(settings.data_db_url),
                    "data_db_host": settings.data_db_host,
                    "data_db_port": str(settings.data_db_port),
                    "data_db_name": settings.data_db_name,
                    "data_db_user": settings.data_db_user,
                    "data_db_password": "***MASKED***",
                },
                "Metadata Database": {
                    "meta_db_url": self._mask_password(settings.meta_db_url),
                    "meta_db_host": settings.meta_db_host,
                    "meta_db_port": str(settings.meta_db_port),
                    "meta_db_name": settings.meta_db_name,
                    "meta_db_user": settings.meta_db_user,
                    "meta_db_password": "***MASKED***",
                },
                "Storage": {
                    "storage_backend": settings.storage_backend,
                    "storage_path": settings.storage_path,
                    "s3_bucket": settings.s3_bucket or "Not configured",
                    "s3_endpoint": settings.s3_endpoint or "Not configured",
                    "s3_access_key": "***MASKED***" if settings.s3_access_key else "Not configured",
                    "s3_secret_key": "***MASKED***" if settings.s3_secret_key else "Not configured",
                },
                "S3 Image Storage": {
                    "s3_images_bucket": settings.s3_images_bucket or "Not configured",
                    "s3_images_endpoint": settings.s3_images_endpoint or "Not configured",
                    "s3_images_region": settings.s3_images_region or "Not configured",
                    "s3_images_access_key": "***MASKED***" if settings.s3_images_access_key else "Not configured",
                    "s3_images_secret_key": "***MASKED***" if settings.s3_images_secret_key else "Not configured",
                    "presigned_url_expiration": f"{settings.presigned_url_expiration}s",
                },
                "Task Queue": {
                    "task_queue_backend": settings.task_queue_backend,
                    "celery_broker_url": self._mask_password(settings.celery_broker_url) if settings.celery_broker_url else "Not configured",
                },
                "Defaults": {
                    "default_query_timeout": f"{settings.default_query_timeout}s",
                    "max_pdf_size_mb": f"{settings.max_pdf_size_mb}MB",
                    "cache_ttl_minutes": f"{settings.cache_ttl_minutes}min",
                },
                "Authentication": {
                    "api_base_url": auth_config.api_base_url,
                    "jwt_public_key_configured": "Yes" if auth_config.jwt_public_key else "No (INSECURE!)",
                },
            }
            
            self.config_data = config
            self.config_error = ""
            
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            self.config_error = str(e)
            self.config_data = {}
    
    @rx.event
    async def load_reports_structure(self):
        """Load the list of report names from the reports folder."""
        try:
            reports_path = Path(settings.reports_path)
            
            if not reports_path.exists():
                self.reports_error = f"Reports path does not exist: {reports_path}"
                self.report_names = []
                return
            
            names = []
            
            # Iterate through report directories
            for report_dir in sorted(reports_path.iterdir()):
                if report_dir.is_dir() and not report_dir.name.startswith('.'):
                    names.append(report_dir.name)
            
            self.report_names = names
            self.reports_error = ""
            
        except Exception as e:
            logger.error(f"Error loading reports structure: {e}")
            self.reports_error = str(e)
            self.report_names = []
    
    @staticmethod
    def _mask_password(url: str | None) -> str:
        """Mask password in URL."""
        if not url:
            return "Not configured"
        
        # Simple masking - replace password with ***
        if '@' in url and ':' in url:
            parts = url.split('@')
            if len(parts) == 2:
                prefix = parts[0]
                if ':' in prefix:
                    user_pass = prefix.split(':')
                    if len(user_pass) >= 2:
                        # Reconstruct with masked password
                        scheme_user = ':'.join(user_pass[:-1])
                        return f"{scheme_user}:***MASKED***@{parts[1]}"
        
        return url
    
