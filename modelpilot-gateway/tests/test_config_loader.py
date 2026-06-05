import logging
from pathlib import Path

from fastapi.testclient import TestClient

from app import logging_config
from app.config_loader import EXAMPLE_CONFIG_PATH, ensure_config_exists, load_config
from app.main import app
from app.utils import mask_api_key


def test_loads_example_config() -> None:
    config = load_config(
        config_path=EXAMPLE_CONFIG_PATH,
        example_config_path=EXAMPLE_CONFIG_PATH,
    )

    assert config.server.host == "127.0.0.1"
    assert config.models["cheap_model"].enabled is False
    assert config.virtual_models["smart-auto"].enabled is True
    assert config.users["default_user"].api_key == "sk-modelpilot-test-key"


def test_missing_config_is_created_from_example(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"

    created_path = ensure_config_exists(
        config_path=config_path,
        example_config_path=EXAMPLE_CONFIG_PATH,
    )
    config = load_config(
        config_path=created_path,
        example_config_path=EXAMPLE_CONFIG_PATH,
    )

    assert created_path == config_path
    assert config_path.exists()
    assert config.server.port == 8000


def test_mask_api_key_does_not_leak_full_key() -> None:
    raw_key = "sk-1234567890abcdef"
    masked_key = mask_api_key(raw_key)

    assert masked_key == "sk-1...cdef"
    assert raw_key not in masked_key
    assert mask_api_key("") == ""


def test_logging_masks_api_key_in_file(tmp_path: Path, monkeypatch) -> None:
    raw_key = "sk-1234567890abcdef"
    config = load_config(
        config_path=EXAMPLE_CONFIG_PATH,
        example_config_path=EXAMPLE_CONFIG_PATH,
    )
    monkeypatch.setattr(logging_config, "LOGS_DIR", tmp_path)

    log_file = logging_config.setup_logging(config)
    logging.getLogger("tests").info("configured api key: %s", raw_key)
    for handler in logging.getLogger().handlers:
        handler.flush()

    content = log_file.read_text(encoding="utf-8")
    assert raw_key not in content
    assert "sk-1...cdef" in content


def test_health_endpoint_still_available() -> None:
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "ModelPilot Gateway",
        "version": "0.1.0",
    }
