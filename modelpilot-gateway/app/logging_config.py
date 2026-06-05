"""Logging configuration helpers for ModelPilot Gateway."""

import logging
import re
from datetime import datetime
from pathlib import Path

from app.schemas import AppConfig
from app.utils import mask_api_key


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOGS_DIR = PROJECT_ROOT / "logs"
API_KEY_PATTERN = re.compile(r"\bsk-[A-Za-z0-9_-]{6,}\b")


class ApiKeyMaskingFilter(logging.Filter):
    """Mask API keys before log records reach handlers."""

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        record.msg = API_KEY_PATTERN.sub(
            lambda match: mask_api_key(match.group(0)),
            message,
        )
        record.args = ()
        return True


def setup_logging(config: AppConfig) -> Path:
    """Configure console and file logging, returning the log file path."""
    log_level_name = config.server.log_level.upper()
    log_level = getattr(logging, log_level_name, logging.INFO)

    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOGS_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(module)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    masking_filter = ApiKeyMaskingFilter()

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.addFilter(masking_filter)

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.addFilter(masking_filter)

    root_logger = logging.getLogger()
    old_handlers = list(root_logger.handlers)
    root_logger.handlers.clear()
    for handler in old_handlers:
        handler.close()

    root_logger.setLevel(log_level)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    return log_file


def get_logger(name: str) -> logging.Logger:
    """Return a standard library logger."""
    return logging.getLogger(name)
