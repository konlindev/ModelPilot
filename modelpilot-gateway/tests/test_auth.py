from datetime import datetime
from typing import Any

from fastapi.testclient import TestClient

from app.main import app
from app.quota import InMemoryQuotaManager
from app.schemas import AppConfig


DEFAULT_HEADERS = {"Authorization": "Bearer sk-allowed-user-key"}


def make_auth_config(
    *,
    enabled: bool = True,
    allowed_models: list[str] | None = None,
    ip_allowlist: list[str] | None = None,
    ip_denylist: list[str] | None = None,
    request_per_minute: int = 60,
    token_daily_limit: int = 0,
    token_monthly_limit: int = 0,
    trust_proxy_headers: bool = True,
) -> AppConfig:
    return AppConfig.model_validate(
        {
            "server": {
                "host": "127.0.0.1",
                "port": 8000,
                "language": "zh-CN",
                "log_level": "INFO",
                "trust_proxy_headers": trust_proxy_headers,
            },
            "models": {
                "cheap_model": {
                    "enabled": True,
                    "provider": "openai",
                    "model": "gpt-test-mini",
                    "base_url": "https://backend.example.com/v1",
                    "api_key": "sk-test-backend-key",
                },
                "strong_model": {
                    "enabled": True,
                    "provider": "openai",
                    "model": "gpt-test-strong",
                    "base_url": "https://backend.example.com/v1",
                    "api_key": "sk-test-backend-key",
                },
                "disabled_model": {
                    "enabled": False,
                    "provider": "openai",
                    "model": "disabled-backend",
                    "base_url": "https://backend.example.com/v1",
                    "api_key": "sk-test-backend-key",
                },
            },
            "virtual_models": {
                "smart-auto": {
                    "enabled": True,
                    "strategy": "manual-placeholder",
                    "candidate_models": ["cheap_model", "strong_model"],
                }
            },
            "classifier": {
                "enabled": False,
                "default_virtual_model": "smart-auto",
            },
            "validation": {
                "enabled": False,
                "max_prompt_chars": 20000,
            },
            "users": {
                "default_user": {
                    "enabled": enabled,
                    "name": "Default User",
                    "api_key": "sk-allowed-user-key",
                    "ip_allowlist": ip_allowlist or [],
                    "ip_denylist": ip_denylist or [],
                    "token_daily_limit": token_daily_limit,
                    "token_monthly_limit": token_monthly_limit,
                    "request_per_minute": request_per_minute,
                    "allowed_hours": [datetime.now().hour],
                    "allowed_models": allowed_models or ["cheap_model", "smart-auto"],
                    "allowed_task_types": ["chat"],
                    "allow_stream": False,
                    "allow_auto_upgrade": False,
                }
            },
        }
    )


def install_config(monkeypatch, config: AppConfig) -> None:
    import app.main as main_module

    monkeypatch.setattr(main_module, "APP_CONFIG", config)
    monkeypatch.setattr(main_module, "quota_manager", InMemoryQuotaManager())


def install_mock_backend(monkeypatch) -> None:
    import app.main as main_module

    class MockOpenAIClient:
        async def chat_completions(self, request_payload, model_config) -> dict[str, Any]:
            return {
                "id": "chatcmpl-test",
                "object": "chat.completion",
                "created": 1710000000,
                "model": model_config.model,
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "ok"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 5,
                    "completion_tokens": 3,
                    "total_tokens": 8,
                },
            }

    monkeypatch.setattr(main_module, "openai_client", MockOpenAIClient())


def post_chat(client: TestClient, headers: dict[str, str] | None = None):
    return client.post(
        "/v1/chat/completions",
        headers=headers or {},
        json={
            "model": "cheap_model",
            "messages": [{"role": "user", "content": "hello"}],
        },
    )


def test_missing_api_key_returns_401(monkeypatch) -> None:
    install_config(monkeypatch, make_auth_config())
    client = TestClient(app)

    response = client.get("/v1/models")

    assert response.status_code == 401


def test_wrong_api_key_returns_401(monkeypatch) -> None:
    install_config(monkeypatch, make_auth_config())
    client = TestClient(app)

    response = client.get("/v1/models", headers={"x-api-key": "sk-wrong-key"})

    assert response.status_code == 401


def test_disabled_user_returns_401(monkeypatch) -> None:
    install_config(monkeypatch, make_auth_config(enabled=False))
    client = TestClient(app)

    response = client.get("/v1/models", headers=DEFAULT_HEADERS)

    assert response.status_code == 401


def test_model_not_allowed_returns_403(monkeypatch) -> None:
    install_config(monkeypatch, make_auth_config(allowed_models=["strong_model"]))
    client = TestClient(app)

    response = post_chat(client, DEFAULT_HEADERS)

    assert response.status_code == 403


def test_ip_denylist_returns_403(monkeypatch) -> None:
    install_config(monkeypatch, make_auth_config(ip_denylist=["203.0.113.10"]))
    client = TestClient(app)

    response = client.get(
        "/v1/models",
        headers={**DEFAULT_HEADERS, "X-Forwarded-For": "203.0.113.10"},
    )

    assert response.status_code == 403


def test_ip_allowlist_mismatch_returns_403(monkeypatch) -> None:
    install_config(monkeypatch, make_auth_config(ip_allowlist=["198.51.100.7"]))
    client = TestClient(app)

    response = client.get(
        "/v1/models",
        headers={**DEFAULT_HEADERS, "X-Forwarded-For": "203.0.113.10"},
    )

    assert response.status_code == 403


def test_request_per_minute_limit_returns_429(monkeypatch) -> None:
    install_config(monkeypatch, make_auth_config(request_per_minute=1))
    install_mock_backend(monkeypatch)
    client = TestClient(app)

    first_response = post_chat(client, DEFAULT_HEADERS)
    second_response = post_chat(client, DEFAULT_HEADERS)

    assert first_response.status_code == 200
    assert second_response.status_code == 429


def test_models_only_returns_user_allowed_models(monkeypatch) -> None:
    install_config(
        monkeypatch,
        make_auth_config(allowed_models=["cheap_model", "smart-auto"]),
    )
    client = TestClient(app)

    response = client.get("/v1/models", headers=DEFAULT_HEADERS)

    assert response.status_code == 200
    model_ids = {item["id"] for item in response.json()["data"]}
    assert model_ids == {"cheap_model", "smart-auto"}
