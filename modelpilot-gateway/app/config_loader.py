"""Configuration loading placeholders for ModelPilot Gateway."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config.json"
EXAMPLE_CONFIG_PATH = PROJECT_ROOT / "config.example.json"


def get_default_config_path() -> Path:
    """Return the default runtime config path."""
    return DEFAULT_CONFIG_PATH

