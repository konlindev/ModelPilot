"""FastAPI application entrypoint for ModelPilot Gateway."""

import logging
import time
import uuid
from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app import __version__
from app.backend_clients import BackendClientError, OpenAICompatibleClient
from app.config_loader import load_config
from app.logging_config import setup_logging
from app.schemas import (
    ChatCompletionRequest,
    ErrorResponse,
    HealthResponse,
    ModelInfo,
    ModelListResponse,
)

APP_CONFIG = load_config()
LOG_FILE_PATH = setup_logging(APP_CONFIG)
logger = logging.getLogger(__name__)
logger.info("ModelPilot Gateway starting with log file: %s", LOG_FILE_PATH)

app = FastAPI(
    title="ModelPilot Gateway",
    version=__version__,
)
openai_client = OpenAICompatibleClient()


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Return basic service health information."""
    return HealthResponse(
        status="ok",
        service="ModelPilot Gateway",
        version=__version__,
    )


@app.get("/v1/models", response_model=ModelListResponse)
def list_models() -> ModelListResponse:
    """Return enabled real and virtual models."""
    model_items: list[ModelInfo] = []

    for model_id, model_config in APP_CONFIG.models.items():
        if model_config.enabled:
            model_items.append(
                ModelInfo(
                    id=model_id,
                    modelpilot={
                        "type": "real_model",
                        "backend_model": model_config.model or model_id,
                    },
                )
            )

    for model_id, model_config in APP_CONFIG.virtual_models.items():
        if model_config.enabled:
            model_items.append(
                ModelInfo(
                    id=model_id,
                    modelpilot={
                        "type": "virtual_model",
                        "strategy": model_config.strategy,
                    },
                )
            )

    return ModelListResponse(data=model_items)


@app.post("/v1/chat/completions", response_model=None)
async def chat_completions(request: ChatCompletionRequest) -> Any:
    """Forward non-streaming chat completions requests to enabled real models."""
    request_id = str(uuid.uuid4())
    requested_model = request.model
    start_time = time.perf_counter()

    if request.stream:
        return _error_response(
            status_code=400,
            message="streaming not implemented in this phase",
            code="streaming_not_implemented",
        )

    if requested_model == "smart-auto":
        return _error_response(
            status_code=400,
            message="smart-auto will be implemented in Phase 4",
            code="smart_auto_not_implemented",
        )

    model_config = APP_CONFIG.models.get(requested_model)
    if model_config is None or not model_config.enabled:
        return _error_response(
            status_code=404,
            message=f"model not found or disabled: {requested_model}",
            code="model_not_found",
        )

    backend_model = model_config.model or requested_model
    request_payload = request.model_dump(exclude_none=True)

    try:
        response_data = await openai_client.chat_completions(
            request_payload=request_payload,
            model_config=model_config,
        )
    except BackendClientError as exc:
        elapsed_ms = _elapsed_ms(start_time)
        logger.warning(
            "request_id=%s requested_model=%s backend_model=%s elapsed_ms=%s failure=%s",
            request_id,
            requested_model,
            backend_model,
            elapsed_ms,
            exc,
        )
        return _error_response(
            status_code=502,
            message="backend request failed",
            code="backend_request_failed",
        )

    response_data["modelpilot"] = {
        "request_id": request_id,
        "routed_model": requested_model,
        "backend_model": backend_model,
        "route_reason": "direct_model",
        "classifier_used": False,
        "auto_upgrade_used": False,
    }

    elapsed_ms = _elapsed_ms(start_time)
    logger.info(
        "request_id=%s requested_model=%s backend_model=%s elapsed_ms=%s success=true",
        request_id,
        requested_model,
        backend_model,
        elapsed_ms,
    )

    return response_data


def _error_response(status_code: int, message: str, code: str) -> JSONResponse:
    error = ErrorResponse(
        error={
            "message": message,
            "type": "invalid_request_error",
            "code": code,
        }
    )
    return JSONResponse(status_code=status_code, content=error.model_dump())


def _elapsed_ms(start_time: float) -> int:
    return int((time.perf_counter() - start_time) * 1000)
