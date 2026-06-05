"""Response validation for ModelPilot Gateway."""

import json
from dataclasses import dataclass
from typing import Any

from app.schemas import AppConfig, ChatCompletionRequest


@dataclass(frozen=True)
class ValidationResult:
    """Result of validating a backend model response."""

    passed: bool
    reason: str
    severity: str


def validate_model_response(
    response_json: dict[str, Any] | None,
    request: ChatCompletionRequest,
    config: AppConfig,
) -> ValidationResult:
    """Validate a backend model response with lightweight checks."""
    if not response_json:
        return ValidationResult(False, "empty response", "high")

    backend_error = _backend_error_text(response_json)
    if backend_error:
        backend_error_lower = backend_error.lower()
        if "rate limit" in backend_error_lower or "rate_limit" in backend_error_lower:
            return ValidationResult(False, "backend rate limit error", "medium")
        if (
            "context length" in backend_error_lower
            or "maximum context" in backend_error_lower
            or "context_length_exceeded" in backend_error_lower
        ):
            return ValidationResult(False, "backend context length exceeded", "high")
        return ValidationResult(False, f"backend error: {backend_error}", "medium")

    choices = response_json.get("choices")
    if not isinstance(choices, list) or not choices:
        return ValidationResult(False, "choices missing or empty", "high")

    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    if not isinstance(message, dict):
        return ValidationResult(False, "message missing", "high")

    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        return ValidationResult(False, "message.content empty", "high")

    stripped_content = content.strip()
    if len(stripped_content) < config.validation.min_response_chars:
        return ValidationResult(False, "response shorter than min_response_chars", "medium")

    if _is_json_mode(request) and not _is_valid_json(stripped_content):
        return ValidationResult(False, "invalid JSON response", "high")

    lowered_content = stripped_content.lower()
    for word in config.validation.banned_words:
        if word and word.lower() in lowered_content:
            return ValidationResult(False, f"banned word detected: {word}", "high")

    for word in config.validation.competitor_brand_words:
        if word and word.lower() in lowered_content:
            return ValidationResult(False, f"competitor brand detected: {word}", "medium")

    return ValidationResult(True, "ok", "low")


def _is_json_mode(request: ChatCompletionRequest) -> bool:
    response_format = request.model_extra.get("response_format") if request.model_extra else None
    if isinstance(response_format, dict):
        response_type = response_format.get("type")
        if response_type in {"json_object", "json_schema"}:
            return True

    text = "\n".join(_content_to_text(message.content) for message in request.messages)
    return "strict json" in text.lower()


def _is_valid_json(text: str) -> bool:
    try:
        json.loads(text)
    except json.JSONDecodeError:
        return False
    return True


def _backend_error_text(response_json: dict[str, Any]) -> str:
    error = response_json.get("error")
    if error is None:
        return ""
    if isinstance(error, str):
        return error
    if isinstance(error, dict):
        for key in ("message", "code", "type"):
            value = error.get(key)
            if isinstance(value, str) and value:
                return value
    return str(error)


def _content_to_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    return str(content)
