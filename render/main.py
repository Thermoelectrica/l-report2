"""Main entry point for initializing the render service."""

import asyncio
import logging

from .database import close_db, init_db
from .services.query_executor import query_executor
from .services.render_service import render_service

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


async def initialize():
    """Initialize all services."""
    logger.info("Initializing render service...")

    # Initialize database
    await init_db()
    logger.info("Database initialized")

    # Initialize query executor
    await query_executor.initialize()
    logger.info("Query executor initialized")

    logger.info("Render service ready")


async def shutdown():
    """Shutdown all services."""
    logger.info("Shutting down render service...")

    # Close query executor
    await query_executor.close()
    logger.info("Query executor closed")

    # Close database
    await close_db()
    logger.info("Database closed")

    logger.info("Render service shutdown complete")


if __name__ == "__main__":
    # Example usage
    async def main():
        await initialize()

        try:
            # List reports
            reports = render_service.listReports()
            print(f"\nAvailable reports ({len(reports)}):")
            for report in reports:
                print(f"  - {report.id}: {report.name}")

            if reports:
                # Get metadata for first report
                report_id = reports[0].id
                metadata = render_service.getReportMetadata(report_id)
                print(f"\nMetadata for '{metadata.name}':")
                print(f"  Description: {metadata.description}")
                print(f"  Version: {metadata.version}")
                print(f"  Parameters: {len(metadata.parameters)}")
                for param in metadata.parameters:
                    print(f"    - {param.name} ({param.type}): {param.description}")

        finally:
            await shutdown()

    asyncio.run(main())
