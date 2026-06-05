# modelpilot-gateway

ModelPilot Gateway is the Python backend gateway for ModelPilot.

Current scope includes FastAPI basics, config loading, logging, API key authentication, basic user permissions, in-memory quotas, rule-based `smart-auto` routing, lightweight classifier-assisted routing, response validation, automatic tier upgrade, and non-streaming OpenAI-compatible forwarding for enabled real models.

Not included yet: database persistence, Redis, native Ollama implementation, Web UI, or streaming forwarding.

## Requirements

- Python 3.10+
- FastAPI
- Uvicorn
- Pydantic v2
- httpx
- pytest

## Install

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Run

```powershell
python -m uvicorn app.main:app --reload
```

Health check:

```text
http://127.0.0.1:8000/health
```

## Configure A Backend

Edit `config.json` and enable one real model under `models`.

```json
{
  "models": {
    "cheap_model": {
      "enabled": true,
      "provider": "openai",
      "tier": "cheap",
      "max_context_tokens": 8000,
      "model": "gpt-4o-mini",
      "base_url": "https://api.openai.com/v1",
      "api_key": "sk-your-real-backend-api-key"
    }
  }
}
```

If `base_url` ends with `/v1`, requests are sent to `/v1/chat/completions`.

## Configure Model Tiers

`smart-auto` uses `tier` and `max_context_tokens` from each real model.

```json
{
  "models": {
    "cheap_model": {
      "enabled": true,
      "tier": "cheap",
      "max_context_tokens": 8000
    },
    "mid_model": {
      "enabled": true,
      "tier": "mid",
      "max_context_tokens": 32000
    },
    "strong_model": {
      "enabled": true,
      "tier": "strong",
      "max_context_tokens": 128000
    }
  }
}
```

Supported tier values are `cheap`, `mid`, and `strong`.

## Configure The Classifier

The classifier is optional and disabled by default. It asks a configured OpenAI-compatible backend for strict JSON classification. If the classifier fails, times out, or returns invalid JSON, the request falls back to the Phase 4 rule route.

Use Ollama's OpenAI-compatible endpoint:

```json
{
  "models": {
    "ollama_local": {
      "enabled": true,
      "provider": "ollama",
      "tier": "cheap",
      "max_context_tokens": 4096,
      "model": "qwen2.5:7b",
      "base_url": "http://127.0.0.1:11434/v1",
      "api_key": ""
    }
  },
  "classifier": {
    "enabled": true,
    "backend_model": "ollama_local",
    "timeout_seconds": 20,
    "min_confidence": 0.7,
    "default_virtual_model": "smart-auto"
  }
}
```

Use any OpenAI-compatible model:

```json
{
  "models": {
    "classifier_model": {
      "enabled": true,
      "provider": "openai",
      "tier": "cheap",
      "max_context_tokens": 8000,
      "model": "gpt-4o-mini",
      "base_url": "https://api.openai.com/v1",
      "api_key": "sk-your-classifier-key"
    }
  },
  "classifier": {
    "enabled": true,
    "backend_model": "classifier_model",
    "timeout_seconds": 20,
    "min_confidence": 0.7,
    "default_virtual_model": "smart-auto"
  }
}
```

The classifier only recommends `task_type`, `risk_level`, `complexity`, `needs_json`, `recommended_tier`, and `confidence`. Final model selection still checks rules, enabled models, context limits, and user `allowed_models`.

## Configure Validation And Auto Upgrade

Validation runs on `smart-auto` responses when `validation.enabled=true`. Direct real-model requests are validated only when `validation.apply_to_direct_model=true`.

```json
{
  "validation": {
    "enabled": true,
    "auto_upgrade_enabled": true,
    "apply_to_direct_model": false,
    "min_response_chars": 5,
    "banned_words": [],
    "competitor_brand_words": [],
    "max_prompt_chars": 20000
  }
}
```

Auto upgrade follows the tier order `cheap -> mid -> strong`. It only runs when `validation.auto_upgrade_enabled=true`, the user has `allow_auto_upgrade=true`, and the next model is enabled and included in the user's `allowed_models`.

Validation failures that can trigger upgrade:

- Empty response.
- Missing or empty `choices`.
- Empty `message.content`.
- Content shorter than `validation.min_response_chars`.
- Invalid JSON when `response_format.type` is `json_object` or `json_schema`, or when the prompt asks for strict JSON.
- Content containing `banned_words`.
- Content containing `competitor_brand_words`.
- Backend error text indicating rate limit.
- Backend error text indicating context length exceeded.

The response `modelpilot` object includes `validation_passed`, `validation_reason`, `auto_upgrade_used`, and `upgrade_chain`.

## Configure Users

Add or update users under `users` in `config.json`.

```json
{
  "users": {
    "default_user": {
      "enabled": true,
      "name": "Default User",
      "api_key": "sk-modelpilot-test-key",
      "ip_allowlist": [],
      "ip_denylist": [],
      "token_daily_limit": 0,
      "token_monthly_limit": 0,
      "request_per_minute": 60,
      "allowed_hours": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23],
      "allowed_models": ["cheap_model", "mid_model", "strong_model", "ollama_local", "smart-auto"],
      "allowed_task_types": ["chat"],
      "allow_stream": false,
      "allow_auto_upgrade": true
    }
  }
}
```

`token_daily_limit`, `token_monthly_limit`, and `request_per_minute` are enforced in memory. The counters reset when the process restarts.

By default, `server.trust_proxy_headers` is `false` and the gateway uses `request.client.host` for IP checks. If it is set to `true`, the first IP in `X-Forwarded-For` is used.

## OpenAI-Compatible APIs

Both `/v1/models` and `/v1/chat/completions` require an API key. Use either `Authorization: Bearer ...` or `x-api-key`.

List models available to the current user:

```powershell
curl http://127.0.0.1:8000/v1/models `
  -H "Authorization: Bearer sk-modelpilot-test-key"
```

Create a non-streaming chat completion:

```powershell
curl -X POST http://127.0.0.1:8000/v1/chat/completions `
  -H "Authorization: Bearer sk-modelpilot-test-key" `
  -H "Content-Type: application/json" `
  -d '{"model":"cheap_model","messages":[{"role":"user","content":"hello"}]}'
```

Use `smart-auto`:

```powershell
curl -X POST http://127.0.0.1:8000/v1/chat/completions `
  -H "Authorization: Bearer sk-modelpilot-test-key" `
  -H "Content-Type: application/json" `
  -d '{"model":"smart-auto","messages":[{"role":"user","content":"Write an Amazon listing title"}]}'
```

The response includes a `modelpilot` metadata object with request id, routed model, backend model, task type, route reason, and classifier fields.

## smart-auto Rules

Current rule routing is intentionally simple:

- `translate` routes as `translation`, usually cheap tier.
- `summarize` routes as `summary`, short summaries usually cheap tier.
- `rewrite` routes as `rewrite`, usually cheap tier.
- `JSON` or `extract` routes as `json_extraction`, usually mid tier.
- `Amazon`, `Walmart`, or `listing` routes as `product_copywriting`, usually mid tier.
- `code`, `python`, `javascript`, or `debug` routes as `code_generation`, usually strong tier.
- `strategy` routes as `strategy_analysis`, usually strong tier.
- `legal` or `contract` routes as `legal_or_policy`, usually strong tier.
- Unknown requests default to mid tier.

If estimated tokens exceed `cheap_model.max_context_tokens`, the router upgrades to mid tier. If estimated tokens exceed `mid_model.max_context_tokens`, it upgrades to strong tier. Disabled models and models outside the user's `allowed_models` are skipped.

## Test

```powershell
python -m pytest
```

## Current Scope

Implemented:

- `GET /health`
- Config loading and default config creation
- Console and file logging
- API key masking in logs
- API key auth through `Authorization: Bearer` and `x-api-key`
- User enable/disable checks
- User model allowlist checks
- IP allowlist and denylist checks
- Allowed hour checks
- In-memory request-per-minute and token quota checks
- `GET /v1/models` filtered by authenticated user permissions
- Non-streaming `POST /v1/chat/completions` for enabled real models
- Rule-based `smart-auto` routing for enabled real models
- Optional lightweight classifier guidance for `smart-auto`
- Response validation for model outputs
- Automatic `cheap -> mid -> strong` tier upgrade after validation failure
- Basic OpenAI-compatible backend forwarding

Not implemented in this stage:

- Streaming responses
- Persistent quota storage
- Database integration
- Redis integration
- Native Ollama implementation
