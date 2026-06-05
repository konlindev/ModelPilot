# Codex 项目约定

本项目对应 GitHub 公开仓库 `konlindev/ModelPilot`。

每次完成代码更新后：

1. 不直接把功能更新提交到 `main`。
2. 创建 `main-update-yyyyMMdd-HHmmss` 格式的更新分支。
3. 在 `docs/updates/` 下新增一份更新说明，写清楚本次变更内容、影响范围和验证方式。
4. 提交改动并推送更新分支到 GitHub。

推荐使用：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\sync-github.ps1 -Summary "本次更新说明"
```

不要把 GitHub Personal Access Token、API Key、`.env` 或其他密钥写入仓库。
