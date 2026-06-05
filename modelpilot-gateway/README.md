# modelpilot-gateway

ModelPilot Gateway 的 Python 后端基础骨架。

本阶段只提供 FastAPI 项目基础结构、健康检查接口和 pytest 测试环境，不包含模型路由、分类器、自动升级、数据库、Redis、Ollama 或 OpenAI 转发逻辑。

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

Then open:

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

## Test

```powershell
python -m pytest
```

## Current Scope

Implemented:

- FastAPI app creation
- `GET /health`
- Basic Pydantic response schema
- pytest health endpoint test
- Placeholder modules for future gateway components

Not implemented in this stage:

- Model routing
- Request classifier
- Automatic upgrade logic
- Startup scripts
- Database integration
- Redis integration
- Ollama integration
- OpenAI forwarding

