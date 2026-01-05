#!/usr/bin/env python3
"""
Minimal App Runner entry point that ensures health checks pass
before loading the full application.
"""
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

logger.info("=" * 60)
logger.info("Starting Tesla Fleet Discovery API")
logger.info("=" * 60)

try:
    logger.info("Importing dashboard_api module...")
    from dashboard_api import app
    logger.info("Successfully imported dashboard_api")
except Exception as e:
    logger.error(f"FATAL: Failed to import dashboard_api: {e}", exc_info=True)
    sys.exit(1)

logger.info("Application ready to serve requests")
