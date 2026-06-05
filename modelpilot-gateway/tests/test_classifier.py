import pytest
from fastapi import HTTPException

from app import classifier
from app.router_engine import select_model_by_rules
from app.schemas import AppConfig, ChatCompletionRequest


def make_classifier_config(
    *,
    classifier_enabled: bool = True,
    allowed_models: list[str] | None = None,
) -> AppConfig:
    return AppConfig.model_validate(
        {
            "server": {
                "host": "127.0.0.1",
                "port": 8000,
                "language": "zh-CN",
                "log_level": "INFO",
                "trust_proxy_headers": False,
            },
            "models": {
                "cheap_model": {
                    "enabled": True,
                    "provider": "openai",
                    "tier": "cheap",
                    "max_context_tokens": 8000,
                    "model": "gpt-cheap",
                    "base_url": "https://backend.example.com/v1",
                    "api_key": "sk-test-backend-key",
                },
                "mid_model": {
                    "enabled": True,
                    "provider": "openai",
                    "tier": "mid",
                    "max_context_tokens": 32000,
                    "model": "gpt-mid",
                    "base_url": "https://backend.example.com/v1",
                    "api_key": "sk-test-backend-key",
                },
                "strong_model": {
                    "enabled": True,
                    "provider": "openai",
                    "tier": "strong",
                    "max_context_tokens": 128000,
                    "model": "gpt-strong",
                    "base_url": "https://backend.example.com/v1",
                    "api_key": "sk-test-backend-key",
                },
                "ollama_local": {
                    "enabled": True,
                    "provider": "ollama",
                    "tier": "cheap",
                    "max_context_tokens": 4096,
                    "model": "qwen2.5:7b",
                    "base_url": "http://127.0.0.1:11434/v1",
                    "api_key": "",
                },
            },
            "virtual_models": {
                "smart-auto": {
                    "enabled": True,
                    "strategy": "rules-with-classifier",
                    "candidate_models": ["cheap_model", "mid_model", "strong_model"],
                }
            },
            "classifier": {
                "enabled": classifier_enabled,
                "backend_model": "ollama_local",
                "timeout_seconds": 20,
                "min_confidence": 0.7,
                "default_virtual_model": "smart-auto",
            },
            "validation": {
                "enabled": False,
                "max_prompt_chars": 20000,
            },
            "users": {
                "classifier_user": {
                    "enabled": True,
                    "name": "Classifier User",
                    "api_key": "sk-classifier-user-key",
                    "ip_allowlist": [],
                    "ip_denylist": [],
                    "token_daily_limit": 0,
                    "token_monthly_limit": 0,
                    "request_per_minute": 60,
                    "allowed_hours": list(range(24)),
                    "allowed_models": allowed_models
                    or ["smart-auto", "cheap_model", "mid_model", "strong_model"],
                    "allowed_task_types": ["chat"],
                    "allow_stream": False,
                    "allow_auto_upgrade": False,
                }
            },
        }
    )


def make_request(content: str) -> ChatCompletionRequest:
    return ChatCompletionRequest.model_validate(
        {
            "model": "smart-auto",
            "messages": [{"role": "user", "content": content}],
        }
    )


def route(content: str, config: AppConfig):
    return select_model_by_rules(
        request=make_request(content),
        user=config.users["classifier_user"],
        config=config,
        estimated_tokens=100,
    )


def test_classifier_disabled_does_not_call_classifier(monkeypatch) -> None:
    def fail_if_called(messages, config):
        raise AssertionError("classifier should not be called")

    monkeypatch.setattr(classifier, "classify_request", fail_if_called)
    decision = route("rewrite this text", make_classifier_config(classifier_enabled=False))

    assert decision.routed_model_name == "cheap_model"
    assert decision.classifier_enabled is False
    assert decision.classifier_used is False


def test_classifier_valid_json_influences_route(monkeypatch) -> None:
    result = classifier.parse_classifier_json(
        """
        {
          "task_type": "json_extraction",
          "risk_level": "medium",
          "complexity": "medium",
          "needs_json": true,
          "recommended_tier": "mid",
          "confidence": 0.91
        }
        """
    )

    monkeypatch.setattr(classifier, "classify_request", lambda messages, config: result)
    decision = route("rewrite this text", make_classifier_config())

    assert decision.routed_model_name == "mid_model"
    assert decision.task_type == "json_extraction"
    assert decision.classifier_used is True
    assert decision.classifier_success is True


def test_classifier_invalid_json_falls_back_to_rule_route(monkeypatch) -> None:
    result = classifier.parse_classifier_json("not json")

    monkeypatch.setattr(classifier, "classify_request", lambda messages, config: result)
    decision = route("rewrite this text", make_classifier_config())

    assert decision.routed_model_name == "cheap_model"
    assert decision.classifier_used is False
    assert decision.classifier_success is False
    assert decision.fallback_to_rule_route is True


def test_classifier_exception_falls_back_to_rule_route(monkeypatch) -> None:
    def raise_timeout(messages, config):
        raise TimeoutError("classifier timed out")

    monkeypatch.setattr(classifier, "classify_request", raise_timeout)
    decision = route("rewrite this text", make_classifier_config())

    assert decision.routed_model_name == "cheap_model"
    assert decision.classifier_used is False
    assert decision.fallback_to_rule_route is True


def test_high_risk_classification_routes_to_strong(monkeypatch) -> None:
    result = classifier.ClassificationResult(
        task_type="rewrite",
        risk_level="high",
        complexity="low",
        needs_json=False,
        recommended_tier="cheap",
        confidence=0.95,
    )

    monkeypatch.setattr(classifier, "classify_request", lambda messages, config: result)
    decision = route("rewrite this text", make_classifier_config())

    assert decision.routed_model_name == "strong_model"
    assert "risk_level=high" in decision.route_reason


def test_high_risk_without_strong_permission_returns_403(monkeypatch) -> None:
    result = classifier.ClassificationResult(
        task_type="rewrite",
        risk_level="high",
        complexity="low",
        needs_json=False,
        recommended_tier="cheap",
        confidence=0.95,
    )

    monkeypatch.setattr(classifier, "classify_request", lambda messages, config: result)
    config = make_classifier_config(allowed_models=["smart-auto", "cheap_model", "mid_model"])

    with pytest.raises(HTTPException) as exc_info:
        route("rewrite this text", config)

    assert exc_info.value.status_code == 403
