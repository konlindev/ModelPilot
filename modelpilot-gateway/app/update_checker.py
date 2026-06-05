"""GitHub update checker used by startup scripts.

This module intentionally uses only the Python standard library so startup
scripts can run it before third-party requirements are installed.
"""

from __future__ import annotations

import argparse
import base64
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[2]
GATEWAY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = GATEWAY_ROOT / "config.json"
EXAMPLE_CONFIG_PATH = GATEWAY_ROOT / "config.example.json"


OutputFunc = Callable[[str], None]


@dataclass
class GitHubUpdateSettings:
    """Resolved GitHub update settings."""

    update_check_enabled: bool = True
    remote: str = "origin"
    branch: str = "main"
    repo_url: str = "https://github.com/konlindev/ModelPilot.git"
    token: str = ""
    protect_config: bool = True
    protected_paths: tuple[str, ...] = ("modelpilot-gateway/config.json",)


@dataclass
class UpdateCheckResult:
    """Result returned by the update checker."""

    status: str
    message: str
    local_commit: str | None = None
    remote_commit: str | None = None


def check_for_updates(
    *,
    repo_root: Path = PROJECT_ROOT,
    config_path: Path = DEFAULT_CONFIG_PATH,
    output: OutputFunc = print,
) -> UpdateCheckResult:
    """Fetch the configured GitHub branch and fast-forward when possible."""
    repo_root = Path(repo_root)
    settings = load_update_settings(config_path)

    if not settings.update_check_enabled:
        result = UpdateCheckResult("disabled", "GitHub update check is disabled.")
        output(result.message)
        return result

    if not (repo_root / ".git").exists():
        result = UpdateCheckResult("skipped", f"Git repository not found: {repo_root}")
        output(result.message)
        return result

    remote_ref = f"{settings.remote}/{settings.branch}"
    git_auth_args = _git_auth_args(settings.token)

    output("Checking GitHub repository for updates...")
    fetch_result = _run_git(
        ["fetch", settings.remote, settings.branch],
        repo_root,
        auth_args=git_auth_args,
        check=False,
    )
    if fetch_result.returncode != 0:
        result = UpdateCheckResult(
            "skipped",
            "GitHub update check failed; continuing with local code.",
        )
        output(result.message)
        return result

    local_commit = _git_stdout(["rev-parse", "HEAD"], repo_root)
    remote_commit = _git_stdout(["rev-parse", remote_ref], repo_root)
    if not local_commit or not remote_commit:
        result = UpdateCheckResult(
            "skipped",
            f"Unable to resolve local or remote commit for {remote_ref}.",
            local_commit=local_commit,
            remote_commit=remote_commit,
        )
        output(result.message)
        return result

    if local_commit == remote_commit:
        result = UpdateCheckResult(
            "no_update",
            "Local code is already up to date.",
            local_commit=local_commit,
            remote_commit=remote_commit,
        )
        output(result.message)
        return result

    if not _is_ancestor(local_commit, remote_ref, repo_root):
        result = UpdateCheckResult(
            "skipped",
            "Remote branch is not a fast-forward update; continuing with local code.",
            local_commit=local_commit,
            remote_commit=remote_commit,
        )
        output(result.message)
        return result

    protected_paths = settings.protected_paths if settings.protect_config else ()
    dirty_paths = _dirty_paths(repo_root)
    unsafe_dirty_paths = [
        path for path in dirty_paths if not _is_protected_path(path, protected_paths)
    ]
    if unsafe_dirty_paths:
        result = UpdateCheckResult(
            "skipped",
            "Local non-config changes exist; skip auto update to avoid overwriting work.",
            local_commit=local_commit,
            remote_commit=remote_commit,
        )
        output(result.message)
        return result

    protected_snapshots = _snapshot_paths(repo_root, protected_paths)
    _restore_git_version(repo_root, protected_paths)

    merge_result = _run_git(
        ["merge", "--ff-only", remote_ref],
        repo_root,
        auth_args=git_auth_args,
        check=False,
    )
    _restore_snapshots(repo_root, protected_snapshots)

    if merge_result.returncode != 0:
        result = UpdateCheckResult(
            "skipped",
            "Auto update failed during fast-forward; local config was restored.",
            local_commit=local_commit,
            remote_commit=remote_commit,
        )
        output(result.message)
        return result

    result = UpdateCheckResult(
        "updated",
        f"Updated local code from {local_commit[:7]} to {remote_commit[:7]}.",
        local_commit=local_commit,
        remote_commit=remote_commit,
    )
    output(result.message)
    if protected_paths:
        output("Local config file was preserved.")
    return result


def load_update_settings(config_path: Path = DEFAULT_CONFIG_PATH) -> GitHubUpdateSettings:
    """Load GitHub update settings from config.json or config.example.json."""
    config_path = Path(config_path)
    source_path = config_path if config_path.exists() else EXAMPLE_CONFIG_PATH

    try:
        config_data = json.loads(source_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        config_data = {}

    github_data = config_data.get("github") if isinstance(config_data, dict) else {}
    if not isinstance(github_data, dict):
        github_data = {}

    protected_paths = github_data.get("protected_paths") or [
        "modelpilot-gateway/config.json"
    ]
    return GitHubUpdateSettings(
        update_check_enabled=bool(github_data.get("update_check_enabled", True)),
        remote=str(github_data.get("remote") or "origin"),
        branch=str(github_data.get("branch") or "main"),
        repo_url=str(
            github_data.get("repo_url")
            or "https://github.com/konlindev/ModelPilot.git"
        ),
        token=str(github_data.get("token") or ""),
        protect_config=bool(github_data.get("protect_config", True)),
        protected_paths=tuple(str(path) for path in protected_paths),
    )


def _git_auth_args(token: str) -> list[str]:
    if not token:
        return []
    basic = base64.b64encode(f"x-access-token:{token}".encode("ascii")).decode("ascii")
    return ["-c", f"http.https://github.com/.extraheader=AUTHORIZATION: basic {basic}"]


def _run_git(
    args: list[str],
    cwd: Path,
    *,
    auth_args: list[str] | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    command = ["git", *(auth_args or []), *args]
    return subprocess.run(
        command,
        cwd=cwd,
        check=check,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _git_stdout(args: list[str], cwd: Path) -> str | None:
    result = _run_git(args, cwd, check=False)
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _is_ancestor(local_commit: str, remote_ref: str, repo_root: Path) -> bool:
    result = _run_git(
        ["merge-base", "--is-ancestor", local_commit, remote_ref],
        repo_root,
        check=False,
    )
    return result.returncode == 0


def _dirty_paths(repo_root: Path) -> list[str]:
    result = _run_git(["status", "--porcelain"], repo_root, check=False)
    paths: list[str] = []
    for line in result.stdout.splitlines():
        if not line:
            continue
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        paths.append(path.replace("\\", "/"))
    return paths


def _is_protected_path(path: str, protected_paths: Iterable[str]) -> bool:
    normalized = path.replace("\\", "/")
    return any(normalized == protected.replace("\\", "/") for protected in protected_paths)


def _snapshot_paths(repo_root: Path, paths: Iterable[str]) -> dict[str, bytes | None]:
    snapshots: dict[str, bytes | None] = {}
    for relative_path in paths:
        target = repo_root / relative_path
        snapshots[relative_path] = target.read_bytes() if target.exists() else None
    return snapshots


def _restore_git_version(repo_root: Path, paths: Iterable[str]) -> None:
    for relative_path in paths:
        _run_git(["checkout", "--", relative_path], repo_root, check=False)


def _restore_snapshots(repo_root: Path, snapshots: dict[str, bytes | None]) -> None:
    for relative_path, content in snapshots.items():
        target = repo_root / relative_path
        if content is None:
            target.unlink(missing_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check GitHub for ModelPilot updates")
    parser.add_argument("--repo-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    args = parser.parse_args()

    try:
        check_for_updates(repo_root=args.repo_root, config_path=args.config)
    except Exception as exc:  # pragma: no cover - startup should continue.
        print(f"GitHub update check failed; continuing with local code: {exc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
