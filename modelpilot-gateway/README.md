# ModelPilot Gateway

## 中文说明

### 项目是什么

ModelPilot Gateway 是一个企业 AI 模型调度与成本治理网关。它提供 OpenAI-compatible API，对上游业务暴露统一的 `/v1/models` 和 `/v1/chat/completions`，对下游连接 OpenAI-compatible 后端、Ollama OpenAI-compatible endpoint 或其他兼容服务。

当前 MVP 已包含：配置加载、日志、API Key 鉴权、基础权限、内存额度、`smart-auto` 规则路由、轻量分类器建议、结果校验和 `cheap -> mid -> strong` 自动升级。

### 架构说明

```text
Client / SDK
  -> ModelPilot Gateway
    -> Auth and user permissions
    -> Quota checks
    -> smart-auto rule router
    -> optional lightweight classifier
    -> OpenAI-compatible backend model
    -> response validation
    -> optional auto upgrade
```

核心模块：

- `app/main.py`：FastAPI 入口和 OpenAI-compatible API。
- `app/config_loader.py`：加载并校验 `config.json`。
- `app/auth.py`：API Key、IP、时间和模型权限。
- `app/quota.py`：内存版频率和 token 额度。
- `app/router_engine.py`：`smart-auto` 规则路由和升级模型选择。
- `app/classifier.py`：可选轻量分类器。
- `app/validators.py`：响应校验和升级触发条件。
- `app/backend_clients.py`：OpenAI-compatible 后端请求。
- `app/logging_config.py`：控制台和文件日志。

### Windows 启动方式

双击或在 PowerShell/CMD 中运行：

```powershell
.\start_windows.bat
```

脚本会检查 Python，必要时尝试使用 `winget install Python.Python.3.12`，然后创建 `.venv`、安装依赖，并启动：

```powershell
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Linux 启动方式

首次使用：

```bash
chmod +x start_linux.sh
./start_linux.sh
```

脚本会检查 `python3`、`venv` 和 `pip`，尽量通过 `apt`、`dnf` 或 `yum` 安装缺失依赖，然后创建 `.venv`、安装依赖并启动服务。

### 如何配置 OpenAI-compatible 后端模型

编辑 `config.json` 的 `models`：

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

如果 `base_url` 是 `https://api.example.com/v1`，网关会请求 `https://api.example.com/v1/chat/completions`。

### 如何配置 Ollama

Ollama 需要启用 OpenAI-compatible endpoint，例如：

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
  }
}
```

也可以把 `classifier.backend_model` 设置为 `ollama_local`，让 Ollama 作为轻量分类器。

### 如何新增用户 API Key

在 `config.json` 的 `users` 下新增用户：

```json
{
  "users": {
    "team_user": {
      "enabled": true,
      "name": "Team User",
      "api_key": "sk-team-user-key",
      "ip_allowlist": [],
      "ip_denylist": [],
      "token_daily_limit": 0,
      "token_monthly_limit": 0,
      "request_per_minute": 60,
      "allowed_hours": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23],
      "allowed_models": ["smart-auto", "cheap_model", "mid_model", "strong_model"],
      "allowed_task_types": ["chat"],
      "allow_stream": false,
      "allow_auto_upgrade": true
    }
  }
}
```

客户端可使用：

```text
Authorization: Bearer sk-team-user-key
```

或：

```text
x-api-key: sk-team-user-key
```

### 如何配置权限

常用权限字段：

- `enabled`：用户是否启用。
- `allowed_models`：用户可访问的模型，如 `["smart-auto", "cheap_model"]`。
- `ip_allowlist`：非空时只允许列表内 IP。
- `ip_denylist`：拒绝列表内 IP。
- `allowed_hours`：允许访问的小时，范围 `0-23`。
- `request_per_minute`：每分钟请求数限制。
- `token_daily_limit` / `token_monthly_limit`：内存版 token 日/月额度，`0` 表示不限。
- `allow_auto_upgrade`：是否允许校验失败后自动升级模型。

如果部署在反向代理后面，默认不信任 `X-Forwarded-For`。需要时设置：

```json
{
  "server": {
    "trust_proxy_headers": true
  }
}
```

### 如何作为 OpenAI Base URL 使用

ModelPilot Gateway 对外提供 OpenAI-compatible base URL：

```text
http://localhost:8000/v1
```

模型名可以使用真实模型别名，例如 `cheap_model`，也可以使用虚拟模型 `smart-auto`。

### curl 示例

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer sk-modelpilot-test-key" \
  -H "Content-Type: application/json" \
  -d '{"model":"smart-auto","messages":[{"role":"user","content":"Say hello in one sentence."}]}'
```

### Python openai SDK 示例

```python
from openai import OpenAI

client = OpenAI(
    api_key="sk-modelpilot-test-key",
    base_url="http://localhost:8000/v1"
)

resp = client.chat.completions.create(
    model="smart-auto",
    messages=[
        {"role": "user", "content": "Say hello in one sentence."}
    ]
)

print(resp.choices[0].message.content)
```

### 常见问题

`/v1/models` 返回空列表：
检查后端模型是否 `enabled=true`，以及当前用户 `allowed_models` 是否包含对应模型。

请求返回 401：
检查是否传入 `Authorization: Bearer ...` 或 `x-api-key`，以及用户是否 enabled。

请求返回 403：
通常是模型不在 `allowed_models`、IP 不允许、当前小时不允许，或没有可升级的高阶模型。

请求返回 `validation_failed`：
模型输出未通过基础校验，且无法继续升级到更高模型。

日志在哪里：
日志写入 `logs/YYYYMMDD_HHMMSS.log`，同时输出到控制台。

### 当前 MVP 限制

- 不支持 streaming。
- 不支持数据库持久化。
- 不支持 Redis 分布式额度。
- 不支持 Web UI。
- 不支持语义缓存。
- token 统计为估算值，且服务重启后清零。
- Ollama 仅通过 OpenAI-compatible endpoint 接入，未实现 native Ollama API。

### 后续路线图

- Redis：分布式限流和额度统计。
- PostgreSQL：用户、模型、账单和审计日志持久化。
- streaming：支持 OpenAI-compatible streaming。
- Web UI：模型、用户、额度和日志管理界面。
- 语义缓存：对重复请求进行缓存命中和成本优化。

## English

### What Is ModelPilot Gateway

ModelPilot Gateway is a Python FastAPI gateway for enterprise AI model routing and cost governance. It exposes OpenAI-compatible endpoints while routing requests to configured backend models.

### Quick Start

Windows:

```powershell
.\start_windows.bat
```

Linux:

```bash
chmod +x start_linux.sh
./start_linux.sh
```

Manual start:

```bash
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Config Backend Models

Enable a backend model in `config.json`:

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

### Use As OpenAI-Compatible base_url

Set your SDK base URL to:

```text
http://localhost:8000/v1
```

Example model names: `smart-auto`, `cheap_model`, `mid_model`, `strong_model`.

### Current Limitations

- No streaming yet.
- No persistent quota store yet.
- No database or Web UI yet.
- No semantic cache yet.
- Quota counters are in memory and reset on restart.
