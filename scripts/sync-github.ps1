param(
  [string]$Summary = "",
  [string]$BaseBranch = "main",
  [string]$BranchName = "",
  [switch]$NoPush
)

$ErrorActionPreference = "Stop"

function Invoke-Git {
  param(
    [Parameter(Mandatory = $true)]
    [string[]]$Arguments
  )

  & git @Arguments
  if ($LASTEXITCODE -ne 0) {
    throw "git $($Arguments -join ' ') failed with exit code $LASTEXITCODE"
  }
}

$repoRoot = (& git rev-parse --show-toplevel).Trim()
if (-not $repoRoot) {
  throw "当前目录不是 Git 仓库。"
}

Set-Location $repoRoot

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
if ([string]::IsNullOrWhiteSpace($BranchName)) {
  $BranchName = "main-update-$stamp"
}

$statusBefore = (& git status --short) -join [Environment]::NewLine
if ([string]::IsNullOrWhiteSpace($statusBefore)) {
  Write-Host "没有检测到需要同步的改动。"
  exit 0
}

Invoke-Git @("fetch", "origin", $BaseBranch, "--prune")
Invoke-Git @("switch", $BaseBranch)
Invoke-Git @("pull", "--ff-only", "origin", $BaseBranch)
Invoke-Git @("switch", "-c", $BranchName)

$noteDir = Join-Path $repoRoot "docs\updates"
New-Item -ItemType Directory -Force $noteDir | Out-Null
$notePath = Join-Path $noteDir "$stamp.md"

if ([string]::IsNullOrWhiteSpace($Summary)) {
  $Summary = "代码更新 $stamp"
}

$changedFiles = (& git status --short) -join [Environment]::NewLine
$note = @"
# $Summary

- 时间：$stamp
- 分支：$BranchName
- 基准分支：$BaseBranch

## 主要变更

请根据本次提交内容补充业务说明。

## 变更文件

````text
$changedFiles
````

## 验证方式

请补充已执行的验证命令或人工检查结果。
"@

Set-Content -Path $notePath -Value $note -Encoding UTF8

Invoke-Git @("add", "-A")
$staged = (& git diff --cached --name-status) -join [Environment]::NewLine
if ([string]::IsNullOrWhiteSpace($staged)) {
  Write-Host "没有可提交的暂存改动。"
  exit 0
}

Invoke-Git @("commit", "-m", $Summary)

if ($NoPush) {
  Write-Host "已创建本地更新分支 $BranchName，按要求跳过推送。"
  exit 0
}

$token = $env:GITHUB_TOKEN
if ([string]::IsNullOrWhiteSpace($token)) {
  $token = $env:GH_TOKEN
}

if ([string]::IsNullOrWhiteSpace($token)) {
  Invoke-Git @("push", "-u", "origin", $BranchName)
} else {
  Invoke-Git @(
    "-c",
    "http.https://github.com/.extraheader=AUTHORIZATION: bearer $token",
    "push",
    "-u",
    "origin",
    $BranchName
  )
}

Write-Host "已同步到 GitHub 分支：$BranchName"
