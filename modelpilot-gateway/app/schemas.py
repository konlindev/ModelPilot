"""Pydantic schemas for ModelPilot Gateway."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    """Response model for the health endpoint."""

    status: str
    service: str
    version: str


class ChatMessage(BaseModel):
    """OpenAI-compatible chat message."""

    model_config = ConfigDict(extra="allow")

    role: str
    content: str | list[Any] | None = None
    name: str | None = None


class ChatCompletionRequest(BaseModel):
    """OpenAI-compatible chat completion request."""

    model_config = ConfigDict(extra="allow")

    model: str
    messages: list[ChatMessage]
    stream: bool = False
    temperature: float | None = None
    top_p: float | None = None
    max_tokens: int | None = None


class ChatCompletionResponse(BaseModel):
    """OpenAI-compatible chat completion response with ModelPilot metadata."""

    model_config = ConfigDict(extra="allow")

    id: str | None = None
    object: str | None = None
    created: int | None = None
    model: str | None = None
    choices: list[dict[str, Any]] = Field(default_factory=list)
    usage: dict[str, Any] | None = None
    modelpilot: dict[str, Any]


class ModelInfo(BaseModel):
    """OpenAI-compatible model list item."""

    model_config = ConfigDict(extra="allow")

    id: str
    object: str = "model"
    owned_by: str = "modelpilot"
    modelpilot: dict[str, Any] = Field(default_factory=dict)


class ModelListResponse(BaseModel):
    """OpenAI-compatible model list response."""

    object: str = "list"
    data: list[ModelInfo]


class ErrorDetail(BaseModel):
    """OpenAI-compatible error details."""

    message: str
    type: str = "invalid_request_error"
    code: str | None = None


class ErrorResponse(BaseModel):
    """OpenAI-compatible error response."""

    error: ErrorDetail


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
