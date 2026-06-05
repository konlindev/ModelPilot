"""Configuration loading for ModelPilot Gateway."""

import json
import shutil
from json import JSONDecodeError
from typing import Any

from pathlib import Path

from pydantic import ValidationError

from app.schemas import AppConfig


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config.json"
EXAMPLE_CONFIG_PATH = PROJECT_ROOT / "config.example.json"


class ConfigLoadError(RuntimeError):
    """Raised when configuration cannot be loaded or validated."""


def get_default_config_path() -> Path:
    """Return the default runtime config path."""
    return DEFAULT_CONFIG_PATH


def ensure_config_exists(
    config_path: Path | None = None,
    example_config_path: Path | None = None,
) -> Path:
    """Create config.json from config.example.json when it is missing."""
    target_path = config_path or DEFAULT_CONFIG_PATH
    source_path = example_config_path or EXAMPLE_CONFIG_PATH

    target_path = Path(target_path)
    source_path = Path(source_path)

    if target_path.exists():
        return target_path

    if not source_path.exists():
        raise ConfigLoadError(
            f"Config file is missing and example config was not found: {source_path}"
        )

    try:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, target_path)
    except OSError as exc:
        raise ConfigLoadError(
            f"Failed to create config file from example: {target_path}"
        ) from exc

    return target_path


def validate_basic_config(config_data: dict[str, Any]) -> AppConfig:
    """Validate basic application config structure with Pydantic."""
    try:
        return AppConfig.model_validate(config_data)
    except ValidationError as exc:
        raise ConfigLoadError(f"Invalid config structure: {exc}") from exc


def load_config(
    config_path: Path | None = None,
    example_config_path: Path | None = None,
) -> AppConfig:
    """Load and validate the runtime configuration."""
    target_path = ensure_config_exists(config_path, example_config_path)

    try:
        raw_content = target_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigLoadError(f"Failed to read config file: {target_path}") from exc

    try:
        config_data = json.loads(raw_content)
    except JSONDecodeError as exc:
        raise ConfigLoadError(
            f"Failed to parse JSON config file {target_path}: {exc.msg}"
        ) from exc

    if not isinstance(config_data, dict):
        raise ConfigLoadError(f"Config root must be a JSON object: {target_path}")

    return validate_basic_config(config_data)
