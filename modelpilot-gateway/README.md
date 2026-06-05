# modelpilot-gateway

ModelPilot Gateway is the Python backend gateway for ModelPilot.

Current scope includes FastAPI basics, config loading, logging, API key authentication, basic user permissions, in-memory quotas, and non-streaming OpenAI-compatible forwarding for enabled real models.

Not included yet: smart-auto routing, classifier logic, automatic upgrade, database persistence, Redis, Ollama implementation, or streaming forwarding.

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
      "model": "gpt-4o-mini",
      "base_url": "https://api.openai.com/v1",
      "api_key": "sk-your-real-backend-api-key"
    }
  }
}
```

If `base_url` ends with `/v1`, requests are sent to `/v1/chat/completions`.

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
      "allow_auto_upgrade": false
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

The response includes a `modelpilot` metadata object with request id, routed model, backend model, and routing flags.

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
- Basic OpenAI-compatible backend forwarding

Not implemented in this stage:

- smart-auto routing
- Complex permission policy engine
- Request classifier
- Automatic upgrade logic
- Streaming responses
- Persistent quota storage
- Database integration
- Redis integration
- Ollama implementation
