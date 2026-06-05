"""FastAPI application entrypoint for ModelPilot Gateway."""

import logging
import time
import uuid
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from app import __version__
from app.auth import (
    authenticate_user,
    check_allowed_hours,
    check_ip_permission,
    check_model_permission,
)
from app.backend_clients import BackendClientError, OpenAICompatibleClient
from app.config_loader import load_config
from app.logging_config import setup_logging
from app.quota import InMemoryQuotaManager
from app.router_engine import select_model_by_rules
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
quota_manager = InMemoryQuotaManager()


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Return basic service health information."""
    return HealthResponse(
        status="ok",
        service="ModelPilot Gateway",
        version=__version__,
    )


@app.get("/v1/models", response_model=ModelListResponse)
def list_models(http_request: Request) -> ModelListResponse | JSONResponse:
    """Return enabled models available to the authenticated user."""
    try:
        _, user = _authorize_request(http_request)
    except HTTPException as exc:
        return _exception_response(exc)

    model_items: list[ModelInfo] = []

    for model_id, model_config in APP_CONFIG.models.items():
        if model_config.enabled and _is_model_allowed(user.allowed_models, model_id):
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
        if model_config.enabled and _is_model_allowed(user.allowed_models, model_id):
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
async def chat_completions(
    http_request: Request,
    request: ChatCompletionRequest,
) -> Any:
    """Forward non-streaming chat completions requests to enabled real models."""
    request_id = str(uuid.uuid4())
    requested_model = request.model
    start_time = time.perf_counter()

    try:
        user_id, user = _authorize_request(http_request)
    except HTTPException as exc:
        return _exception_response(exc)

    if request.stream:
        return _error_response(
            status_code=400,
            message="streaming not implemented in this phase",
            code="streaming_not_implemented",
        )

    try:
        check_model_permission(user, requested_model)
    except HTTPException as exc:
        return _exception_response(exc)

    if not quota_manager.check_rate_limit(user_id, user.request_per_minute):
        return _error_response(
            status_code=429,
            message="request_per_minute quota exceeded",
            code="rate_limit_exceeded",
            error_type="rate_limit_error",
        )

    estimated_prompt_tokens = quota_manager.estimate_tokens_from_messages(
        request.messages
    )
    if not quota_manager.check_token_quota(
        user_name=user_id,
        estimated_tokens=estimated_prompt_tokens,
        daily_limit=user.token_daily_limit,
        monthly_limit=user.token_monthly_limit,
    ):
        return _error_response(
            status_code=429,
            message="token quota exceeded",
            code="token_quota_exceeded",
            error_type="rate_limit_error",
        )

    task_type = "direct_model"
    route_reason = "direct_model"
    routed_model = requested_model
    backend_model = requested_model
    classifier_enabled = False
    classifier_used = False
    classifier_success = False
    classifier_task_type = None
    classifier_recommended_tier = None
    classifier_confidence = None
    fallback_to_rule_route = False

    if requested_model == "smart-auto":
        try:
            route_decision = select_model_by_rules(
                request=request,
                user=user,
                config=APP_CONFIG,
                estimated_tokens=estimated_prompt_tokens,
            )
        except HTTPException as exc:
            return _exception_response(exc)

        routed_model = route_decision.routed_model_name
        backend_model = route_decision.backend_model_name
        task_type = route_decision.task_type
        route_reason = route_decision.route_reason
        classifier_enabled = route_decision.classifier_enabled
        classifier_used = route_decision.classifier_used
        classifier_success = route_decision.classifier_success
        classifier_task_type = route_decision.classifier_task_type
        classifier_recommended_tier = route_decision.classifier_recommended_tier
        classifier_confidence = route_decision.classifier_confidence
        fallback_to_rule_route = route_decision.fallback_to_rule_route
        model_config = APP_CONFIG.models[routed_model]
    else:
        model_config = APP_CONFIG.models.get(requested_model)
        if model_config is None or not model_config.enabled:
            return _error_response(
                status_code=404,
                message=f"model not found or disabled: {requested_model}",
                code="model_not_found",
            )
        backend_model = model_config.model or requested_model

    request_payload = request.model_dump(exclude_none=True)
    request_payload["model"] = backend_model

    try:
        response_data = await openai_client.chat_completions(
            request_payload=request_payload,
            model_config=model_config,
        )
    except BackendClientError as exc:
        elapsed_ms = _elapsed_ms(start_time)
        logger.warning(
            "request_id=%s user=%s requested_model=%s routed_model=%s backend_model=%s task_type=%s route_reason=%s estimated_tokens=%s classifier_enabled=%s classifier_used=%s classifier_success=%s classifier_task_type=%s classifier_recommended_tier=%s classifier_confidence=%s fallback_to_rule_route=%s elapsed_ms=%s failure=%s",
            request_id,
            user_id,
            requested_model,
            routed_model,
            backend_model,
            task_type,
            route_reason,
            estimated_prompt_tokens,
            classifier_enabled,
            classifier_used,
            classifier_success,
            classifier_task_type,
            classifier_recommended_tier,
            classifier_confidence,
            fallback_to_rule_route,
            elapsed_ms,
            exc,
        )
        return _error_response(
            status_code=502,
            message="backend request failed",
            code="backend_request_failed",
        )

    if requested_model == "smart-auto":
        response_data["model"] = requested_model

    response_data["modelpilot"] = {
        "request_id": request_id,
        "routed_model": routed_model,
        "backend_model": backend_model,
        "task_type": task_type,
        "route_reason": route_reason,
        "classifier_enabled": classifier_enabled,
        "classifier_used": classifier_used,
        "classifier_success": classifier_success,
        "classifier_task_type": classifier_task_type,
        "classifier_recommended_tier": classifier_recommended_tier,
        "classifier_confidence": classifier_confidence,
        "fallback_to_rule_route": fallback_to_rule_route,
        "auto_upgrade_used": False,
    }

    elapsed_ms = _elapsed_ms(start_time)
    usage = response_data.get("usage") if isinstance(response_data.get("usage"), dict) else {}
    prompt_tokens = _safe_int(usage.get("prompt_tokens"), estimated_prompt_tokens)
    completion_tokens = _safe_int(usage.get("completion_tokens"), 0)
    quota_manager.record_token_usage(
        user_name=user_id,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
    )
    logger.info(
        "request_id=%s user=%s requested_model=%s routed_model=%s backend_model=%s task_type=%s route_reason=%s estimated_tokens=%s classifier_enabled=%s classifier_used=%s classifier_success=%s classifier_task_type=%s classifier_recommended_tier=%s classifier_confidence=%s fallback_to_rule_route=%s elapsed_ms=%s success=true",
        request_id,
        user_id,
        requested_model,
        routed_model,
        backend_model,
        task_type,
        route_reason,
        estimated_prompt_tokens,
        classifier_enabled,
        classifier_used,
        classifier_success,
        classifier_task_type,
        classifier_recommended_tier,
        classifier_confidence,
        fallback_to_rule_route,
        elapsed_ms,
    )

    return response_data


def _authorize_request(http_request: Request):
    user_id, user = authenticate_user(http_request, APP_CONFIG)
    check_ip_permission(user, http_request, APP_CONFIG)
    check_allowed_hours(user)
    return user_id, user


def _exception_response(exc: HTTPException) -> JSONResponse:
    message = str(exc.detail)
    code = _status_code_to_error_code(exc.status_code)
    error_type = "authentication_error"
    if exc.status_code == 403:
        error_type = "permission_error"
    elif exc.status_code == 429:
        error_type = "rate_limit_error"

    return _error_response(
        status_code=exc.status_code,
        message=message,
        code=code,
        error_type=error_type,
    )


def _error_response(
    status_code: int,
    message: str,
    code: str,
    error_type: str = "invalid_request_error",
) -> JSONResponse:
    error = ErrorResponse(
        error={
            "message": message,
            "type": error_type,
            "code": code,
        }
    )
    return JSONResponse(status_code=status_code, content=error.model_dump())


def _elapsed_ms(start_time: float) -> int:
    return int((time.perf_counter() - start_time) * 1000)


def _is_model_allowed(allowed_models: list[str], model_name: str) -> bool:
    return "*" in allowed_models or model_name in allowed_models


def _status_code_to_error_code(status_code: int) -> str:
    if status_code == 401:
        return "authentication_failed"
    if status_code == 403:
        return "permission_denied"
    if status_code == 429:
        return "rate_limit_exceeded"
    return "request_failed"


def _safe_int(value: Any, fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback
