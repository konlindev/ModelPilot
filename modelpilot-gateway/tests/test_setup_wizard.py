import json
from pathlib import Path

from app.config_loader import EXAMPLE_CONFIG_PATH
from app.schemas import AppConfig
from app.setup_wizard import apply_setup_payload, config_needs_setup, run_text_wizard, save_setup_payload


def test_apply_setup_payload_marks_setup_completed() -> None:
    config_data = json.loads(EXAMPLE_CONFIG_PATH.read_text(encoding="utf-8"))

    updated = apply_setup_payload(config_data, sample_payload())
    config = AppConfig.model_validate(updated)

    assert config.setup.completed is True
    assert config.setup.language == "en"
    assert config.server.language == "en"
    assert config.models["cheap_model"].enabled is True
    assert config.models["cheap_model"].base_url == "https://api.example.com/v1"
    assert config.users["default_user"].api_key == "sk-user-test"
    assert config.users["default_user"].allowed_models == ["cheap_model", "smart-auto"]


def test_save_setup_payload_writes_temp_config(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"

    updated = save_setup_payload(sample_payload(), config_path=config_path)
    written = json.loads(config_path.read_text(encoding="utf-8"))

    assert updated["setup"]["completed"] is True
    assert written["setup"]["completed"] is True
    assert config_needs_setup(config_path) is False


def test_text_wizard_prompts_language_first_and_saves(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    answers = iter(
        [
            "1",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
        ]
    )
    output: list[str] = []

    updated = run_text_wizard(
        config_path=config_path,
        input_func=lambda prompt: next(answers),
        output_func=output.append,
    )

    assert updated is not None
    assert updated["setup"]["completed"] is True
    assert updated["setup"]["language"] == "zh"
    assert "ModelPilot Gateway First-run Setup" in output


def test_completed_setup_skips_prompts(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    save_setup_payload(sample_payload(), config_path=config_path)
    output: list[str] = []

    result = run_text_wizard(
        config_path=config_path,
        input_func=lambda prompt: (_ for _ in ()).throw(AssertionError("prompted")),
        output_func=output.append,
    )

    assert result is None
    assert any("already completed" in line for line in output)


def sample_payload() -> dict:
    return {
        "language": "en",
        "models": {
            "cheap_model": {
                "enabled": True,
                "provider": "openai",
                "tier": "cheap",
                "model": "gpt-cheap",
                "base_url": "https://api.example.com/v1",
                "api_key": "sk-backend-test",
                "max_context_tokens": 8000,
            },
            "mid_model": {"enabled": False},
            "strong_model": {"enabled": False},
            "ollama_local": {"enabled": False},
        },
        "classifier": {
            "enabled": False,
            "backend_model": "ollama_local",
            "timeout_seconds": 20,
            "min_confidence": 0.7,
        },
        "user": {
            "api_key": "sk-user-test",
            "request_per_minute": 30,
            "token_daily_limit": 1000,
            "token_monthly_limit": 30000,
            "allow_auto_upgrade": True,
            "allowed_models": ["cheap_model", "smart-auto"],
        },
    }
