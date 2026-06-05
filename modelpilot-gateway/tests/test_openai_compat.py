from typing import Any

from fastapi.testclient import TestClient

from app.main import app
from app.quota import InMemoryQuotaManager
from app.schemas import AppConfig


AUTH_HEADERS = {"Authorization": "Bearer sk-modelpilot-test-key"}


def make_test_config() -> AppConfig:
    return AppConfig.model_validate(
        {
            "server": {
                "host": "127.0.0.1",
                "port": 8000,
                "language": "zh-CN",
                "log_level": "INFO",
            },
            "models": {
                "cheap_model": {
                    "enabled": True,
                    "provider": "openai",
                    "model": "gpt-test-mini",
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
                    "candidate_models": ["cheap_model"],
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
                    "enabled": True,
                    "name": "Default User",
                    "api_key": "sk-modelpilot-test-key",
                    "allowed_models": ["*"],
                }
            },
        }
    )


def test_models_returns_enabled_real_and_virtual_models(monkeypatch) -> None:
    import app.main as main_module

    monkeypatch.setattr(main_module, "APP_CONFIG", make_test_config())
    monkeypatch.setattr(main_module, "quota_manager", InMemoryQuotaManager())
    client = TestClient(app)

    response = client.get("/v1/models", headers=AUTH_HEADERS)

    assert response.status_code == 200
    model_ids = {item["id"] for item in response.json()["data"]}
    assert model_ids == {"cheap_model", "smart-auto"}


def test_unknown_model_returns_404(monkeypatch) -> None:
    import app.main as main_module

    monkeypatch.setattr(main_module, "APP_CONFIG", make_test_config())
    monkeypatch.setattr(main_module, "quota_manager", InMemoryQuotaManager())
    client = TestClient(app)

    response = client.post(
        "/v1/chat/completions",
        headers=AUTH_HEADERS,
        json={"model": "missing_model", "messages": [{"role": "user", "content": "hi"}]},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "model_not_found"


def test_streaming_returns_400(monkeypatch) -> None:
    import app.main as main_module

    monkeypatch.setattr(main_module, "APP_CONFIG", make_test_config())
    monkeypatch.setattr(main_module, "quota_manager", InMemoryQuotaManager())
    client = TestClient(app)

    response = client.post(
        "/v1/chat/completions",
        headers=AUTH_HEADERS,
        json={
            "model": "cheap_model",
            "stream": True,
            "messages": [{"role": "user", "content": "hi"}],
        },
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "streaming_not_implemented"


def test_smart_auto_returns_400(monkeypatch) -> None:
    import app.main as main_module

    monkeypatch.setattr(main_module, "APP_CONFIG", make_test_config())
    monkeypatch.setattr(main_module, "quota_manager", InMemoryQuotaManager())
    client = TestClient(app)

    response = client.post(
        "/v1/chat/completions",
        headers=AUTH_HEADERS,
        json={"model": "smart-auto", "messages": [{"role": "user", "content": "hi"}]},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "smart_auto_not_implemented"


def test_real_model_forwards_to_openai_compatible_backend(monkeypatch) -> None:
    import app.backend_clients as backend_clients
    import app.main as main_module

    captured: dict[str, Any] = {}

    class MockResponse:
        status_code = 200

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, Any]:
            return {
                "id": "chatcmpl-test",
                "object": "chat.completion",
                "created": 1710000000,
                "model": "gpt-test-mini",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": "hello",
                        },
                        "finish_reason": "stop",
                    }
                ],
            }

    class MockAsyncClient:
        def __init__(self, timeout) -> None:
            captured["timeout"] = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def post(self, url, json, headers):
            captured["url"] = url
            captured["json"] = json
            captured["headers"] = headers
            return MockResponse()

    monkeypatch.setattr(main_module, "APP_CONFIG", make_test_config())
    monkeypatch.setattr(main_module, "quota_manager", InMemoryQuotaManager())
    monkeypatch.setattr(backend_clients.httpx, "AsyncClient", MockAsyncClient)
    client = TestClient(app)

    response = client.post(
        "/v1/chat/completions",
        headers=AUTH_HEADERS,
        json={
            "model": "cheap_model",
            "messages": [{"role": "user", "content": "hello"}],
        },
    )

    assert response.status_code == 200
    assert captured["url"] == "https://backend.example.com/v1/chat/completions"
    assert captured["json"]["model"] == "gpt-test-mini"
    assert captured["headers"]["Authorization"] == "Bearer sk-test-backend-key"
    response_json = response.json()
    assert response_json["choices"][0]["message"]["content"] == "hello"
    assert response_json["modelpilot"]["routed_model"] == "cheap_model"
    assert response_json["modelpilot"]["backend_model"] == "gpt-test-mini"
    assert response_json["modelpilot"]["route_reason"] == "direct_model"
    assert response_json["modelpilot"]["classifier_used"] is False
    assert response_json["modelpilot"]["auto_upgrade_used"] is False
