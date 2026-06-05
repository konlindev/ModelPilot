# ModelPilot

企业 AI 模型调度与成本治理平台  
Enterprise AI model orchestration and cost governance platform.

## 项目简介 / Overview

ModelPilot 用于沉淀企业内部 AI 模型调用、任务调度、成本归集、预算预警与治理策略相关代码。

ModelPilot centralizes code for enterprise AI model invocation, workload scheduling, cost allocation, budget alerts, and governance policies.

当前主要子项目：

- `modelpilot-gateway/`：Python FastAPI 网关，提供 OpenAI-compatible API、用户鉴权、额度控制、`smart-auto` 规则路由、轻量分类器、结果校验和自动升级。

## GitHub 仓库 / GitHub Repository

- 公开仓库 / Public repository: <https://github.com/konlindev/ModelPilot>
- 默认分支 / Default branch: `main`
- 当前代码已合并到 `main`。

## 启动 ModelPilot Gateway

Windows:

```powershell
cd modelpilot-gateway
.\start_windows.bat
```

Linux:

```bash
cd modelpilot-gateway
chmod +x start_linux.sh
./start_linux.sh
```

首次运行时，启动脚本会在安装依赖后进入终端文字向导，先选择中文或英文，然后逐步完成后端模型、分类器、默认用户 API Key、额度和权限配置。

## 部署方式 / Deployment

### Windows 单机部署

适合本地测试、小团队内网部署或 Windows Server 试运行：

```powershell
cd modelpilot-gateway
.\start_windows.bat
```

脚本会自动检查 Python、创建 `.venv`、安装依赖、运行首次配置向导，并启动服务到：

```text
http://localhost:8000
```

### Linux 单机部署

适合 Ubuntu、Debian、CentOS、Rocky Linux 等服务器：

```bash
cd modelpilot-gateway
chmod +x start_linux.sh
./start_linux.sh
```

脚本会尽量使用 `apt`、`dnf` 或 `yum` 安装缺失的 Python 组件，然后启动 FastAPI 服务。

### 手动部署

如果需要自己控制虚拟环境和启动方式，可以手动执行：

```bash
cd modelpilot-gateway
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m app.setup_wizard
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Windows PowerShell 中激活虚拟环境：

```powershell
cd modelpilot-gateway
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install -r requirements.txt
python -m app.setup_wizard
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 生产部署建议

- 将服务部署在内网服务器或受控云服务器上。
- 使用 Nginx、Caddy 或企业网关作为反向代理。
- 使用 HTTPS 保护 API 调用。
- 不要把真实后端 API Key 提交到公开仓库。
- 当前额度统计是内存版，服务重启后会清零；生产环境后续建议接入 Redis 或数据库。

## 配置说明 / Configuration

主配置文件位于：

```text
modelpilot-gateway/config.json
```

首次运行时如果不存在 `config.json`，系统会从 `config.example.json` 自动创建。

主要配置块：

- `server`：服务地址、端口、语言、日志级别、是否信任反向代理 IP 头。
- `models`：真实后端模型配置，例如 `cheap_model`、`mid_model`、`strong_model`、`ollama_local`。
- `virtual_models`：虚拟模型配置，当前默认提供 `smart-auto`。
- `classifier`：轻量分类器配置，可使用 Ollama 或 OpenAI-compatible 后端。
- `validation`：结果校验和自动升级配置。
- `users`：用户 API Key、允许模型、IP 规则、时间规则、频率限制和 token 额度。
- `setup`：首次运行文字向导状态。

OpenAI-compatible 后端模型示例：

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
      "api_key": "sk-your-backend-api-key"
    }
  }
}
```

Ollama 示例：

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

用户 API Key 示例：

```json
{
  "users": {
    "default_user": {
      "enabled": true,
      "name": "Default User",
      "api_key": "sk-modelpilot-test-key",
      "request_per_minute": 60,
      "token_daily_limit": 0,
      "token_monthly_limit": 0,
      "allowed_models": ["smart-auto", "cheap_model", "mid_model", "strong_model"],
      "allow_auto_upgrade": true
    }
  }
}
```

更完整的配置字段说明见：

```text
modelpilot-gateway/config.schema.md
```

## 更新同步 / Update Sync

后续代码更新完成后，建议流程如下：

1. 在本地创建更新分支。
2. 提交代码和更新说明。
3. 推送到 GitHub。
4. 创建 Pull Request 合并到 `main`。

如果使用项目脚本，可以在项目根目录运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\sync-github.ps1 -Summary "本次更新说明 / Update summary"
```

脚本会自动创建更新分支、生成 `docs/updates/` 下的更新说明、提交当前改动，并推送更新分支到 GitHub。

如果 GitHub 凭据未保存在本机，可在运行脚本前临时设置 `GITHUB_TOKEN` 或 `GH_TOKEN` 环境变量。

## 当前 MVP 限制 / Current Limitations

- 暂不支持 streaming。
- 暂无数据库持久化。
- 暂无 Redis 分布式额度。
- 暂无 Web UI。
- token 额度统计为内存版，服务重启后会清零。
