"""Minimal bilingual startup messages."""

from pathlib import Path

from app.schemas import AppConfig


MESSAGES = {
    "zh": {
        "service_starting": "服务启动：ModelPilot Gateway",
        "config_loaded": "配置加载成功",
        "log_file": "日志文件路径",
        "default_api": "默认 API 地址",
        "language": "当前语言",
    },
    "en": {
        "service_starting": "Service starting: ModelPilot Gateway",
        "config_loaded": "Config loaded successfully",
        "log_file": "Log file path",
        "default_api": "Default API URL",
        "language": "Current language",
    },
}


def normalize_language(language: str | None) -> str:
    """Normalize config language to zh or en."""
    value = (language or "en").lower()
    if value.startswith("zh"):
        return "zh"
    return "en"


def startup_messages(config: AppConfig, log_file_path: Path) -> list[str]:
    """Return startup messages in the configured language."""
    language = normalize_language(config.server.language)
    messages = MESSAGES[language]
    api_url = f"http://{config.server.host}:{config.server.port}/v1"

    return [
        f"{messages['service_starting']}",
        f"{messages['config_loaded']}",
        f"{messages['log_file']}: {log_file_path}",
        f"{messages['default_api']}: {api_url}",
        f"{messages['language']}: {language}",
    ]
