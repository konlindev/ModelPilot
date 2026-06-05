"""Lightweight classifier for smart-auto routing suggestions."""

import json
import logging
from dataclasses import dataclass
from typing import Any

import httpx

from app.schemas import AppConfig, ChatMessage, ModelConfig


logger = logging.getLogger(__name__)

TASK_TYPES = {
    "rewrite",
    "translation",
    "summary",
    "classification",
    "product_copywriting",
    "customer_support",
    "json_extraction",
    "code_generation",
    "strategy_analysis",
    "legal_or_policy",
    "unknown",
}
RISK_LEVELS = {"low", "medium", "high"}
COMPLEXITIES = {"low", "medium", "high"}
TIERS = {"cheap", "mid", "strong"}


@dataclass(frozen=True)
class ClassificationResult:
    """Structured classifier output."""

    task_type: str
    risk_level: str
    complexity: str
    needs_json: bool
    recommended_tier: str
    confidence: float


def classify_request(
    messages: list[ChatMessage],
    config: AppConfig,
) -> ClassificationResult | None:
    """Classify a request using the configured OpenAI-compatible backend."""
    if not config.classifier.enabled:
        return None

    backend_model_name = config.classifier.backend_model
    model_config = config.models.get(backend_model_name)
    if model_config is None or not model_config.enabled:
        logger.warning(
            "classifier failed: backend_model=%s is missing or disabled",
            backend_model_name,
        )
        return None

    payload = {
        "model": model_config.model or backend_model_name,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You classify user requests for model routing. "
                    "Return strict JSON only. Do not wrap the JSON in markdown."
                ),
            },
            {"role": "user", "content": build_classifier_prompt(messages)},
        ],
        "temperature": 0,
        "stream": False,
    }

    headers = {"Content-Type": "application/json"}
    if model_config.api_key:
        headers["Authorization"] = f"Bearer {model_config.api_key}"

    try:
        with httpx.Client(timeout=config.classifier.timeout_seconds) as client:
            response = client.post(
                _chat_completions_url(model_config),
                json=payload,
                headers=headers,
            )
            response.raise_for_status()

        response_data = response.json()
        content = _extract_message_content(response_data)
        result = parse_classifier_json(content)
        if result is None:
            logger.warning("classifier failed: invalid JSON classifier response")
        return result
    except (httpx.HTTPError, ValueError, TypeError, KeyError) as exc:
        logger.warning("classifier failed: %s", exc)
        return None


def build_classifier_prompt(messages: list[ChatMessage]) -> str:
    """Build a classifier prompt that asks for strict JSON."""
    user_content = "\n".join(_message_to_text(message) for message in messages)
    user_content = user_content[:12000]

    return (
        "Classify the following chat request. Return strict JSON with exactly this shape:\n"
        "{\n"
        '  "task_type": "rewrite|translation|summary|classification|product_copywriting|customer_support|json_extraction|code_generation|strategy_analysis|legal_or_policy|unknown",\n'
        '  "risk_level": "low|medium|high",\n'
        '  "complexity": "low|medium|high",\n'
        '  "needs_json": true,\n'
        '  "recommended_tier": "cheap|mid|strong",\n'
        '  "confidence": 0.82\n'
        "}\n\n"
        "Chat request:\n"
        f"{user_content}"
    )


def parse_classifier_json(text: str) -> ClassificationResult | None:
    """Parse strict classifier JSON into a ClassificationResult."""
    try:
        data = json.loads(_strip_json_text(text))
    except (TypeError, json.JSONDecodeError):
        return None

    if not isinstance(data, dict):
        return None

    task_type = data.get("task_type")
    risk_level = data.get("risk_level")
    complexity = data.get("complexity")
    recommended_tier = data.get("recommended_tier")
    needs_json = data.get("needs_json")
    confidence = data.get("confidence")

    if task_type not in TASK_TYPES:
        return None
    if risk_level not in RISK_LEVELS:
        return None
    if complexity not in COMPLEXITIES:
        return None
    if recommended_tier not in TIERS:
        return None
    if not isinstance(needs_json, bool):
        return None

    try:
        confidence_value = float(confidence)
    except (TypeError, ValueError):
        return None

    if confidence_value < 0 or confidence_value > 1:
        return None

    return ClassificationResult(
        task_type=task_type,
        risk_level=risk_level,
        complexity=complexity,
        needs_json=needs_json,
        recommended_tier=recommended_tier,
        confidence=confidence_value,
    )


def _chat_completions_url(model_config: ModelConfig) -> str:
    base_url = (model_config.base_url or "").strip().rstrip("/")
    if not base_url:
        raise ValueError("classifier backend base_url is not configured")
    if base_url.endswith("/chat/completions"):
        return base_url
    return f"{base_url}/chat/completions"


def _extract_message_content(response_data: dict[str, Any]) -> str:
    choices = response_data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("classifier backend response has no choices")

    message = choices[0].get("message", {})
    content = message.get("content")
    if not isinstance(content, str):
        raise ValueError("classifier backend response has no text content")

    return content


def _strip_json_text(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`").strip()
        if text.lower().startswith("json"):
            text = text[4:].strip()
    return text


def _message_to_text(message: ChatMessage) -> str:
    return f"{message.role}: {_content_to_text(message.content)}"


def _content_to_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    return str(content)
