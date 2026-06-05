from datetime import datetime
from typing import Any

from fastapi.testclient import TestClient

from app.main import app
from app.quota import InMemoryQuotaManager
from app.schemas import AppConfig, ChatCompletionRequest
from app.validators import validate_model_response


AUTH_HEADERS = {"Authorization": "Bearer sk-validation-user-key"}


def make_validation_config(
    *,
    allow_auto_upgrade: bool = True,
    allowed_models: list[str] | None = None,
    min_response_chars: int = 5,
    banned_words: list[str] | None = None,
    competitor_brand_words: list[str] | None = None,
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
            },
            "virtual_models": {
                "smart-auto": {
                    "enabled": True,
                    "strategy": "rules-with-validation",
                    "candidate_models": ["cheap_model", "mid_model", "strong_model"],
                }
            },
            "classifier": {
                "enabled": False,
                "backend_model": "cheap_model",
                "timeout_seconds": 20,
                "min_confidence": 0.7,
                "default_virtual_model": "smart-auto",
            },
            "validation": {
                "enabled": True,
                "auto_upgrade_enabled": True,
                "apply_to_direct_model": False,
                "min_response_chars": min_response_chars,
                "banned_words": banned_words or [],
                "competitor_brand_words": competitor_brand_words or [],
                "max_prompt_chars": 20000,
            },
            "users": {
                "validation_user": {
                    "enabled": True,
                    "name": "Validation User",
                    "api_key": "sk-validation-user-key",
                    "ip_allowlist": [],
                    "ip_denylist": [],
                    "token_daily_limit": 0,
                    "token_monthly_limit": 0,
                    "request_per_minute": 60,
                    "allowed_hours": [datetime.now().hour],
                    "allowed_models": allowed_models
                    or ["smart-auto", "cheap_model", "mid_model", "strong_model"],
                    "allowed_task_types": ["chat"],
                    "allow_stream": False,
                    "allow_auto_upgrade": allow_auto_upgrade,
                }
            },
        }
    )


def make_request(**extra: Any) -> ChatCompletionRequest:
    payload: dict[str, Any] = {
        "model": "smart-auto",
        "messages": [{"role": "user", "content": "rewrite this text"}],
    }
    payload.update(extra)
    return ChatCompletionRequest.model_validate(payload)


def response_with_content(content: str) -> dict[str, Any]:
    return {
        "id": "chatcmpl-validation",
        "object": "chat.completion",
        "created": 1710000000,
        "model": "backend-model",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 4, "completion_tokens": 2, "total_tokens": 6},
    }


def test_empty_choices_fails_validation() -> None:
    result = validate_model_response(
        {"choices": []},
        make_request(),
        make_validation_config(),
    )

    assert result.passed is False
    assert "choices" in result.reason


def test_empty_content_fails_validation() -> None:
    result = validate_model_response(
        response_with_content(""),
        make_request(),
        make_validation_config(),
    )

    assert result.passed is False
    assert "content" in result.reason


def test_min_response_chars_is_enforced() -> None:
    result = validate_model_response(
        response_with_content("hey"),
        make_request(),
        make_validation_config(min_response_chars=5),
    )

    assert result.passed is False
    assert "min_response_chars" in result.reason


def test_json_mode_rejects_invalid_json() -> None:
    result = validate_model_response(
        response_with_content("not json"),
        make_request(response_format={"type": "json_object"}),
        make_validation_config(),
    )

    assert result.passed is False
    assert result.reason == "invalid JSON response"


def test_banned_words_fail_validation() -> None:
    result = validate_model_response(
        response_with_content("this contains forbidden copy"),
        make_request(),
        make_validation_config(banned_words=["forbidden"]),
    )

    assert result.passed is False
    assert "banned word" in result.reason


def install_mock_backend(monkeypatch, contents: list[str]) -> list[str]:
    import app.main as main_module

    called_models: list[str] = []
    responses = list(contents)

    class MockOpenAIClient:
        async def chat_completions(self, request_payload, model_config) -> dict[str, Any]:
            called_models.append(request_payload["model"])
            content = responses.pop(0)
            return response_with_content(content)

    monkeypatch.setattr(main_module, "openai_client", MockOpenAIClient())
    return called_models


def install_config(monkeypatch, config: AppConfig) -> None:
    import app.main as main_module

    monkeypatch.setattr(main_module, "APP_CONFIG", config)
    monkeypatch.setattr(main_module, "quota_manager", InMemoryQuotaManager())


def post_smart_auto(client: TestClient):
    return client.post(
        "/v1/chat/completions",
        headers=AUTH_HEADERS,
        json={
            "model": "smart-auto",
            "messages": [{"role": "user", "content": "rewrite this text"}],
        },
    )


def test_smart_auto_cheap_failure_upgrades_to_mid(monkeypatch) -> None:
    install_config(monkeypatch, make_validation_config())
    called_models = install_mock_backend(monkeypatch, ["bad", "valid mid response"])
    client = TestClient(app)

    response = post_smart_auto(client)

    assert response.status_code == 200
    response_json = response.json()
    assert called_models == ["gpt-cheap", "gpt-mid"]
    assert response_json["modelpilot"]["auto_upgrade_used"] is True
    assert response_json["modelpilot"]["upgrade_chain"][0]["to_model"] == "mid_model"


def test_mid_failure_upgrades_to_strong(monkeypatch) -> None:
    install_config(monkeypatch, make_validation_config())
    called_models = install_mock_backend(
        monkeypatch,
        ["bad", "bad", "valid strong response"],
    )
    client = TestClient(app)

    response = post_smart_auto(client)

    assert response.status_code == 200
    response_json = response.json()
    assert called_models == ["gpt-cheap", "gpt-mid", "gpt-strong"]
    assert response_json["modelpilot"]["upgrade_chain"][1]["to_model"] == "strong_model"


def test_no_upgrade_when_user_disallows_auto_upgrade(monkeypatch) -> None:
    install_config(monkeypatch, make_validation_config(allow_auto_upgrade=False))
    called_models = install_mock_backend(monkeypatch, ["bad"])
    client = TestClient(app)

    response = post_smart_auto(client)

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "validation_failed"
    assert called_models == ["gpt-cheap"]


def test_no_upgrade_when_higher_model_not_allowed(monkeypatch) -> None:
    install_config(
        monkeypatch,
        make_validation_config(allowed_models=["smart-auto", "cheap_model"]),
    )
    called_models = install_mock_backend(monkeypatch, ["bad"])
    client = TestClient(app)

    response = post_smart_auto(client)

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "validation_failed"
    assert called_models == ["gpt-cheap"]


def test_highest_model_failure_returns_standard_error(monkeypatch) -> None:
    install_config(monkeypatch, make_validation_config())
    called_models = install_mock_backend(monkeypatch, ["bad", "bad", "bad"])
    client = TestClient(app)

    response = post_smart_auto(client)

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "validation_failed"
    assert called_models == ["gpt-cheap", "gpt-mid", "gpt-strong"]
