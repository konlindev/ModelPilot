"""Pydantic schemas for ModelPilot Gateway."""

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    """Response model for the health endpoint."""

    status: str
    service: str
    version: str


class ServerConfig(BaseModel):
    """Basic server and runtime configuration."""

    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    language: str = "zh-CN"
    log_level: str = "INFO"


class ModelConfig(BaseModel):
    """Basic model backend or virtual model configuration."""

    model_config = ConfigDict(extra="allow")

    enabled: bool = False
    provider: str | None = None
    model: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    description: str | None = None
    strategy: str | None = None
    candidate_models: list[str] = Field(default_factory=list)


class UserConfig(BaseModel):
    """Basic user configuration."""

    model_config = ConfigDict(extra="allow")

    enabled: bool = True
    name: str | None = None
    api_key: str


class ClassifierConfig(BaseModel):
    """Classifier feature switch configuration."""

    model_config = ConfigDict(extra="allow")

    enabled: bool = False
    default_virtual_model: str = "smart-auto"


class ValidationConfig(BaseModel):
    """Request validation feature switch configuration."""

    model_config = ConfigDict(extra="allow")

    enabled: bool = False
    max_prompt_chars: int = Field(default=20000, ge=1)


class AppConfig(BaseModel):
    """Top-level application configuration."""

    model_config = ConfigDict(extra="allow")

    server: ServerConfig
    models: dict[str, ModelConfig]
    virtual_models: dict[str, ModelConfig]
    classifier: ClassifierConfig
    validation: ValidationConfig
    users: dict[str, UserConfig]
