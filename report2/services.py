"""Service initialization for the report2 web application."""

import asyncio
import logging

from render.database import init_db
from render.services.query_executor import query_executor

logger = logging.getLogger(__name__)

# Flag to track if services are initialized
_services_initialized = False
_initialization_lock = asyncio.Lock()


async def ensure_services_initialized():
    """Ensure all services are initialized (idempotent)."""
    global _services_initialized

    async with _initialization_lock:
        if not _services_initialized:
            logger.info("Initializing services...")
            try:
                # Initialize database
                await init_db()
                logger.info("Database initialized")

                # Initialize query executor
                await query_executor.initialize()
                logger.info("Query executor initialized")

                _services_initialized = True
                logger.info("All services initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize services: {e}", exc_info=True)
                raise
