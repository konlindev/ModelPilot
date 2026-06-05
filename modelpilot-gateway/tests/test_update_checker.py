import json
import subprocess
from pathlib import Path

from app.update_checker import check_for_updates, load_update_settings


def test_load_update_settings_defaults_to_public_repo_without_token(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text("{}", encoding="utf-8")

    settings = load_update_settings(config_path)

    assert settings.update_check_enabled is True
    assert settings.remote == "origin"
    assert settings.branch == "main"
    assert settings.token == ""
    assert "modelpilot-gateway/config.json" in settings.protected_paths


def test_update_checker_fast_forwards_and_preserves_config(tmp_path: Path) -> None:
    remote = tmp_path / "remote.git"
    source = tmp_path / "source"
    clone = tmp_path / "clone"

    git(tmp_path, "init", "--bare", str(remote))
    source.mkdir()
    git(source, "init")
    git(source, "config", "user.email", "tests@example.com")
    git(source, "config", "user.name", "Tests")
    git(source, "checkout", "-b", "main")

    write_initial_repo(source, "remote-key")
    git(source, "add", ".")
    git(source, "commit", "-m", "initial")
    git(source, "remote", "add", "origin", str(remote))
    git(source, "push", "-u", "origin", "main")

    git(tmp_path, "clone", str(remote), str(clone))
    git(clone, "checkout", "main")
    git(clone, "config", "user.email", "tests@example.com")
    git(clone, "config", "user.name", "Tests")

    clone_config_path = clone / "modelpilot-gateway" / "config.json"
    clone_config = json.loads(clone_config_path.read_text(encoding="utf-8"))
    clone_config["github"]["token"] = "local-token"
    clone_config["users"]["default_user"]["api_key"] = "local-user-key"
    clone_config_path.write_text(
        json.dumps(clone_config, indent=2) + "\n",
        encoding="utf-8",
    )

    (source / "README.md").write_text("# Updated\n", encoding="utf-8")
    source_config = json.loads(
        (source / "modelpilot-gateway" / "config.json").read_text(encoding="utf-8")
    )
    source_config["users"]["default_user"]["api_key"] = "remote-new-key"
    (source / "modelpilot-gateway" / "config.json").write_text(
        json.dumps(source_config, indent=2) + "\n",
        encoding="utf-8",
    )
    git(source, "add", ".")
    git(source, "commit", "-m", "remote update")
    git(source, "push", "origin", "main")

    messages: list[str] = []
    result = check_for_updates(
        repo_root=clone,
        config_path=clone_config_path,
        output=messages.append,
    )

    preserved_config = json.loads(clone_config_path.read_text(encoding="utf-8"))
    assert result.status == "updated"
    assert (clone / "README.md").read_text(encoding="utf-8") == "# Updated\n"
    assert preserved_config["github"]["token"] == "local-token"
    assert preserved_config["users"]["default_user"]["api_key"] == "local-user-key"
    assert any("Local config file was preserved" in message for message in messages)


def write_initial_repo(repo: Path, api_key: str) -> None:
    gateway = repo / "modelpilot-gateway"
    gateway.mkdir()
    config = {
        "github": {
            "update_check_enabled": True,
            "remote": "origin",
            "branch": "main",
            "repo_url": "",
            "token": "",
            "protect_config": True,
            "protected_paths": ["modelpilot-gateway/config.json"],
        },
        "users": {
            "default_user": {
                "api_key": api_key,
            }
        },
    }
    (gateway / "config.json").write_text(
        json.dumps(config, indent=2) + "\n",
        encoding="utf-8",
    )
    (gateway / "config.example.json").write_text(
        json.dumps(config, indent=2) + "\n",
        encoding="utf-8",
    )
    (repo / "README.md").write_text("# Initial\n", encoding="utf-8")


def git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
