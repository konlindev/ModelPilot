"""FastAPI application entrypoint for ModelPilot Gateway."""

import logging

from fastapi import FastAPI

from app import __version__
from app.config_loader import load_config
from app.logging_config import setup_logging
from app.schemas import HealthResponse

APP_CONFIG = load_config()
LOG_FILE_PATH = setup_logging(APP_CONFIG)
logger = logging.getLogger(__name__)
logger.info("ModelPilot Gateway starting with log file: %s", LOG_FILE_PATH)

app = FastAPI(
    title="ModelPilot Gateway",
    version=__version__,
)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Return basic service health information."""
    return HealthResponse(
        status="ok",
        service="ModelPilot Gateway",
        version=__version__,
    )
