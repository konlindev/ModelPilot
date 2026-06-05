"""FastAPI application entrypoint for ModelPilot Gateway."""

from fastapi import FastAPI

from app import __version__
from app.schemas import HealthResponse

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

