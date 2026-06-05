# modelpilot-gateway

ModelPilot Gateway 的 Python 后端基础骨架。

当前阶段提供 FastAPI 基础服务、配置加载、日志系统，以及 OpenAI-compatible 的基础非 streaming 转发接口。暂不包含复杂权限控制、smart-auto 路由、分类器、自动升级、数据库、Redis、Ollama 实现或 streaming 转发。

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

Expected response:

```json
{
  "status": "ok",
  "service": "ModelPilot Gateway",
  "version": "0.1.0"
}
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
      "api_key": "sk-your-real-api-key"
    }
  }
}
```

If `base_url` ends with `/v1`, requests are sent to `/v1/chat/completions`.

## OpenAI-Compatible APIs

List available enabled models:

```powershell
curl http://127.0.0.1:8000/v1/models
```

Create a non-streaming chat completion:

```powershell
curl -X POST http://127.0.0.1:8000/v1/chat/completions `
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

- FastAPI app creation
- `GET /health`
- Config loading and default config creation
- Console and file logging
- API key masking in logs
- `GET /v1/models`
- Non-streaming `POST /v1/chat/completions` for enabled real models
- Basic OpenAI-compatible backend forwarding
- pytest coverage for health, config, logging, and OpenAI-compatible forwarding

Not implemented in this stage:

- smart-auto routing
- Complex authentication or authorization
- Request classifier
- Automatic upgrade logic
- Streaming responses
- Startup scripts
- Database integration
- Redis integration
- Ollama implementation
