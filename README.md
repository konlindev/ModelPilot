# ModelPilot

企业 AI 模型调度与成本治理平台。  
Enterprise AI model orchestration and cost governance platform.

## 项目简介 / Overview

ModelPilot 用于沉淀企业内部 AI 模型调用、任务调度、成本归集、预算预警与治理策略相关代码。  
ModelPilot is designed to centralize code for enterprise AI model invocation, workload scheduling, cost allocation, budget alerts, and governance policies.

## GitHub 仓库 / GitHub Repository

- 公开仓库 / Public repository: <https://github.com/konlindev/ModelPilot>
- 默认分支 / Default branch: `main`
- 更新分支格式 / Update branch format: `main-update-yyyyMMdd-HHmmss`

## 更新同步 / Update Sync

后续代码更新完成后，在项目根目录运行：  
After future code changes, run the following command from the project root:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\sync-github.ps1 -Summary "本次更新说明 / Update summary"
```

脚本会自动完成：  
The script will automatically:

1. 创建新的更新分支。 / Create a new update branch.
2. 生成 `docs/updates/` 下的更新说明。 / Generate an update note under `docs/updates/`.
3. 提交当前改动。 / Commit the current changes.
4. 推送更新分支到 GitHub。 / Push the update branch to GitHub.

如当前环境未保存 GitHub 凭据，可在运行脚本前临时设置 `GITHUB_TOKEN` 或 `GH_TOKEN` 环境变量。  
If GitHub credentials are not stored locally, temporarily set the `GITHUB_TOKEN` or `GH_TOKEN` environment variable before running the script.
