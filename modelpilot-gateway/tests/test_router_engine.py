from datetime import datetime
from typing import Any

from fastapi.testclient import TestClient

from app.main import app
from app.quota import InMemoryQuotaManager
from app.router_engine import select_model_by_rules
from app.schemas import AppConfig, ChatCompletionRequest


AUTH_HEADERS = {"Authorization": "Bearer sk-router-user-key"}


def make_router_config(
    *,
    cheap_enabled: bool = True,
    mid_enabled: bool = True,
    strong_enabled: bool = True,
    cheap_context: int = 8000,
    mid_context: int = 32000,
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
                    "enabled": cheap_enabled,
                    "provider": "openai",
                    "tier": "cheap",
                    "max_context_tokens": cheap_context,
                    "model": "gpt-cheap",
                    "base_url": "https://backend.example.com/v1",
                    "api_key": "sk-test-backend-key",
                },
                "mid_model": {
                    "enabled": mid_enabled,
                    "provider": "openai",
                    "tier": "mid",
                    "max_context_tokens": mid_context,
                    "model": "gpt-mid",
                    "base_url": "https://backend.example.com/v1",
                    "api_key": "sk-test-backend-key",
                },
                "strong_model": {
                    "enabled": strong_enabled,
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
                    "strategy": "rules-v1",
                    "candidate_models": ["cheap_model", "mid_model", "strong_model"],
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
                "router_user": {
                    "enabled": True,
                    "name": "Router User",
                    "api_key": "sk-router-user-key",
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


def route(content: str, config: AppConfig, estimated_tokens: int = 100):
    user = config.users["router_user"]
    return select_model_by_rules(
        request=make_request(content),
        user=user,
        config=config,
        estimated_tokens=estimated_tokens,
    )


def test_rewrite_routes_to_cheap() -> None:
    decision = route("Please rewrite this product sentence.", make_router_config())

    assert decision.routed_model_name == "cheap_model"
    assert decision.task_type == "rewrite"


def test_product_listing_routes_to_mid() -> None:
    decision = route("Write an Amazon listing 标题 and 商品描述.", make_router_config())

    assert decision.routed_model_name == "mid_model"
    assert decision.task_type == "product_copywriting"


def test_code_generation_routes_to_strong() -> None:
    decision = route("Please debug this python code 报错.", make_router_config())

    assert decision.routed_model_name == "strong_model"
    assert decision.task_type == "code_generation"


def test_user_disallows_cheap_falls_back_to_mid() -> None:
    decision = route(
        "rewrite this text",
        make_router_config(allowed_models=["smart-auto", "mid_model", "strong_model"]),
    )

    assert decision.routed_model_name == "mid_model"


def test_disabled_model_is_not_selected() -> None:
    decision = route("rewrite this text", make_router_config(cheap_enabled=False))

    assert decision.routed_model_name == "mid_model"


def test_tokens_over_cheap_context_upgrade_to_mid_or_strong() -> None:
    mid_decision = route(
        "rewrite this text",
        make_router_config(cheap_context=10, mid_context=100),
        estimated_tokens=20,
    )
    strong_decision = route(
        "rewrite this text",
        make_router_config(cheap_context=10, mid_context=30),
        estimated_tokens=40,
    )

    assert mid_decision.routed_model_name == "mid_model"
    assert strong_decision.routed_model_name == "strong_model"


def test_smart_auto_forwards_to_mock_backend(monkeypatch) -> None:
    import app.main as main_module

    captured: dict[str, Any] = {}

    class MockOpenAIClient:
        async def chat_completions(self, request_payload, model_config) -> dict[str, Any]:
            captured["payload"] = request_payload
            captured["backend_model"] = model_config.model
            return {
                "id": "chatcmpl-router",
                "object": "chat.completion",
                "created": 1710000000,
                "model": model_config.model,
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": "listing copy",
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 5,
                    "total_tokens": 15,
                },
            }

    monkeypatch.setattr(main_module, "APP_CONFIG", make_router_config())
    monkeypatch.setattr(main_module, "openai_client", MockOpenAIClient())
    monkeypatch.setattr(main_module, "quota_manager", InMemoryQuotaManager())
    client = TestClient(app)

    response = client.post(
        "/v1/chat/completions",
        headers=AUTH_HEADERS,
        json={
            "model": "smart-auto",
            "messages": [{"role": "user", "content": "Write an Amazon listing"}],
        },
    )

    assert response.status_code == 200
    response_json = response.json()
    assert captured["payload"]["model"] == "gpt-mid"
    assert captured["backend_model"] == "gpt-mid"
    assert response_json["model"] == "smart-auto"
    assert response_json["modelpilot"]["routed_model"] == "mid_model"
    assert response_json["modelpilot"]["backend_model"] == "gpt-mid"
    assert response_json["modelpilot"]["task_type"] == "product_copywriting"
    assert response_json["modelpilot"]["classifier_used"] is False
    assert response_json["modelpilot"]["auto_upgrade_used"] is False
