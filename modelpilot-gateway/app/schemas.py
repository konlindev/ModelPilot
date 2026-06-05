"""Pydantic schemas for ModelPilot Gateway."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Response model for the health endpoint."""

    status: str
    service: str
    version: str

