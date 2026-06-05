"""Text-based first-run setup wizard for ModelPilot Gateway."""

import argparse
import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from app.config_loader import DEFAULT_CONFIG_PATH, ensure_config_exists, load_config
from app.schemas import AppConfig
from app.utils import mask_api_key


MODEL_KEYS = ("cheap_model", "mid_model", "strong_model", "ollama_local")
REAL_MODEL_KEYS = ("cheap_model", "mid_model", "strong_model", "ollama_local")
TIERS = {
    "cheap_model": "cheap",
    "mid_model": "mid",
    "strong_model": "strong",
    "ollama_local": "cheap",
}

InputFunc = Callable[[str], str]
OutputFunc = Callable[[str], None]


def is_setup_completed(config: AppConfig) -> bool:
    """Return whether the first-run text setup has been completed."""
    return bool(config.setup.completed)


def config_needs_setup(config_path: Path | None = None) -> bool:
    """Return True when config.json exists but setup is not completed."""
    config = load_config(config_path=config_path)
    return not is_setup_completed(config)


def run_text_wizard(
    config_path: Path | None = None,
    *,
    force: bool = False,
    input_func: InputFunc = input,
    output_func: OutputFunc = print,
) -> dict[str, Any] | None:
    """Run the interactive text wizard and persist config.json."""
    config_path = ensure_config_exists(config_path)
    config_data = _read_config_data(config_path)
    config = AppConfig.model_validate(config_data)

    if is_setup_completed(config) and not force:
        language = _normalize_language(config.setup.language or config.server.language)
        _say(output_func, language, "setup_already_done")
        _say(output_func, language, "start_hint")
        return None

    language = _prompt_language(input_func, output_func, config)
    _say(output_func, language, "welcome")

    payload = {
        "language": language,
        "models": _prompt_models(config_data, language, input_func, output_func),
        "classifier": _prompt_classifier(config_data, language, input_func, output_func),
        "user": _prompt_user(config_data, language, input_func, output_func),
    }

    _print_review(payload, language, output_func)
    if not _prompt_bool(
        _msg(language, "save_confirm"),
        True,
        input_func,
        output_func,
    ):
        _say(output_func, language, "setup_cancelled")
        return None

    updated = save_setup_payload(payload, config_path=config_path)
    _say(output_func, language, "saved")
    output_func(f"Base URL: http://localhost:8000/v1")
    api_key = updated["users"]["default_user"]["api_key"]
    output_func(f"API Key: {mask_api_key(api_key)}")
    return updated


def save_setup_payload(
    payload: dict[str, Any],
    config_path: Path | None = None,
) -> dict[str, Any]:
    """Merge a wizard payload into config.json and return updated config data."""
    target_path = ensure_config_exists(config_path)
    current_config = _read_config_data(target_path)
    updated = apply_setup_payload(current_config, payload)

    AppConfig.model_validate(updated)
    target_path.write_text(
        json.dumps(updated, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return updated


def apply_setup_payload(config_data: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    """Return config data updated from a text wizard payload."""
    data = deepcopy(config_data)
    language = _normalize_language(str(payload.get("language") or "en"))

    data.setdefault("server", {})["language"] = "zh-CN" if language == "zh" else "en"

    models_payload = payload.get("models") or {}
    models = data.setdefault("models", {})
    for model_key in MODEL_KEYS:
        model_payload = models_payload.get(model_key) or {}
        model_data = models.setdefault(model_key, {})
        model_data["enabled"] = bool(model_payload.get("enabled", model_data.get("enabled", False)))
        model_data["tier"] = model_payload.get("tier") or model_data.get("tier") or TIERS[model_key]
        model_data["provider"] = model_payload.get("provider") or model_data.get("provider") or "openai"

        if "model" in model_payload:
            model_data["model"] = str(model_payload.get("model") or "").strip()
        if "base_url" in model_payload:
            model_data["base_url"] = str(model_payload.get("base_url") or "").strip()
        if "api_key" in model_payload:
            model_data["api_key"] = str(model_payload.get("api_key") or "").strip()
        if "max_context_tokens" in model_payload:
            model_data["max_context_tokens"] = _positive_int(
                model_payload.get("max_context_tokens"),
                int(model_data.get("max_context_tokens") or 8192),
            )

    virtual_models = data.setdefault("virtual_models", {})
    virtual_models.setdefault("smart-auto", {}).update(
        {
            "enabled": True,
            "strategy": "rules-with-classifier-validation",
            "candidate_models": ["cheap_model", "mid_model", "strong_model"],
        }
    )

    classifier_payload = payload.get("classifier") or {}
    classifier = data.setdefault("classifier", {})
    if classifier_payload:
        classifier["enabled"] = bool(classifier_payload.get("enabled", classifier.get("enabled", False)))
        classifier["backend_model"] = str(
            classifier_payload.get("backend_model") or classifier.get("backend_model") or "ollama_local"
        ).strip()
        classifier["timeout_seconds"] = _positive_int(
            classifier_payload.get("timeout_seconds"),
            int(classifier.get("timeout_seconds") or 20),
        )
        classifier["min_confidence"] = float(
            classifier_payload.get("min_confidence", classifier.get("min_confidence", 0.7))
        )

    users = data.setdefault("users", {})
    default_user = users.setdefault("default_user", {})
    user_payload = payload.get("user") or {}
    default_user["enabled"] = True
    default_user["name"] = str(user_payload.get("name") or default_user.get("name") or "Default User")
    default_user["api_key"] = str(
        user_payload.get("api_key") or default_user.get("api_key") or "sk-modelpilot-test-key"
    )
    default_user["request_per_minute"] = _positive_int(
        user_payload.get("request_per_minute"),
        int(default_user.get("request_per_minute") or 60),
    )
    default_user["token_daily_limit"] = _positive_int(
        user_payload.get("token_daily_limit"),
        int(default_user.get("token_daily_limit") or 0),
        allow_zero=True,
    )
    default_user["token_monthly_limit"] = _positive_int(
        user_payload.get("token_monthly_limit"),
        int(default_user.get("token_monthly_limit") or 0),
        allow_zero=True,
    )
    default_user["allow_auto_upgrade"] = bool(
        user_payload.get("allow_auto_upgrade", default_user.get("allow_auto_upgrade", False))
    )
    default_user["allow_stream"] = False
    default_user["allowed_models"] = _allowed_models(
        user_payload.get("allowed_models"),
        data,
    )
    default_user.setdefault("allowed_hours", list(range(24)))
    default_user.setdefault("allowed_task_types", ["chat"])
    default_user.setdefault("ip_allowlist", [])
    default_user.setdefault("ip_denylist", [])

    data.setdefault("setup", {}).update(
        {
            "completed": True,
            "language": language,
            "completed_at": datetime.now().isoformat(timespec="seconds"),
        }
    )
    return data


def _prompt_language(input_func: InputFunc, output_func: OutputFunc, config: AppConfig) -> str:
    default = _normalize_language(config.setup.language or config.server.language)
    output_func("")
    output_func("========================================")
    output_func("ModelPilot Gateway First-run Setup")
    output_func("ModelPilot Gateway 首次运行文字向导")
    output_func("========================================")
    output_func("1. 中文")
    output_func("2. English")
    choice = _prompt_text("请选择界面语言 / Select language [1]: ", "1" if default == "zh" else "2", input_func)
    return "en" if choice.strip() == "2" else "zh"


def _prompt_models(
    config_data: dict[str, Any],
    language: str,
    input_func: InputFunc,
    output_func: OutputFunc,
) -> dict[str, Any]:
    _section(output_func, language, "models_section")
    models_payload: dict[str, Any] = {}
    models = config_data.get("models") or {}

    for model_key in REAL_MODEL_KEYS:
        current = models.get(model_key) or {}
        _line(output_func, f"{model_key} ({current.get('tier') or TIERS[model_key]})")
        enabled = _prompt_bool(
            _msg(language, "enable_model").format(model=model_key),
            bool(current.get("enabled", False)),
            input_func,
            output_func,
        )
        provider = current.get("provider") or ("ollama" if model_key == "ollama_local" else "openai")
        default_base_url = current.get("base_url") or ""
        if model_key == "ollama_local" and default_base_url == "http://127.0.0.1:11434":
            default_base_url = "http://127.0.0.1:11434/v1"

        model_payload = {
            "enabled": enabled,
            "provider": provider,
            "tier": current.get("tier") or TIERS[model_key],
            "max_context_tokens": current.get("max_context_tokens") or 8192,
            "model": current.get("model") or "",
            "base_url": default_base_url,
            "api_key": current.get("api_key") or "",
        }

        if enabled:
            model_payload["model"] = _prompt_text(
                _msg(language, "backend_model_name"),
                str(model_payload["model"]),
                input_func,
            )
            model_payload["base_url"] = _prompt_text(
                _msg(language, "backend_base_url"),
                str(model_payload["base_url"]),
                input_func,
            )
            current_masked = mask_api_key(str(model_payload["api_key"]))
            key_hint = _msg(language, "backend_api_key").format(current=current_masked or _msg(language, "empty"))
            api_key = input_func(key_hint).strip()
            if api_key:
                model_payload["api_key"] = api_key
            model_payload["max_context_tokens"] = _prompt_int(
                _msg(language, "max_context_tokens"),
                int(model_payload["max_context_tokens"]),
                input_func,
                output_func,
                allow_zero=False,
            )

        models_payload[model_key] = model_payload

    if not any(model["enabled"] for model in models_payload.values()):
        _say(output_func, language, "no_model_enabled")

    return models_payload


def _prompt_classifier(
    config_data: dict[str, Any],
    language: str,
    input_func: InputFunc,
    output_func: OutputFunc,
) -> dict[str, Any]:
    _section(output_func, language, "classifier_section")
    current = config_data.get("classifier") or {}
    enabled = _prompt_bool(
        _msg(language, "classifier_enabled"),
        bool(current.get("enabled", False)),
        input_func,
        output_func,
    )
    backend_model = current.get("backend_model") or "ollama_local"
    if enabled:
        backend_model = _prompt_choice(
            _msg(language, "classifier_backend"),
            list(REAL_MODEL_KEYS),
            backend_model,
            input_func,
            output_func,
        )

    return {
        "enabled": enabled,
        "backend_model": backend_model,
        "timeout_seconds": current.get("timeout_seconds") or 20,
        "min_confidence": current.get("min_confidence") or 0.7,
    }


def _prompt_user(
    config_data: dict[str, Any],
    language: str,
    input_func: InputFunc,
    output_func: OutputFunc,
) -> dict[str, Any]:
    _section(output_func, language, "user_section")
    current = (config_data.get("users") or {}).get("default_user") or {}
    api_key = _prompt_text(
        _msg(language, "user_api_key"),
        str(current.get("api_key") or "sk-modelpilot-test-key"),
        input_func,
    )
    request_per_minute = _prompt_int(
        _msg(language, "request_per_minute"),
        int(current.get("request_per_minute") or 60),
        input_func,
        output_func,
        allow_zero=True,
    )
    daily_limit = _prompt_int(
        _msg(language, "daily_limit"),
        int(current.get("token_daily_limit") or 0),
        input_func,
        output_func,
        allow_zero=True,
    )
    monthly_limit = _prompt_int(
        _msg(language, "monthly_limit"),
        int(current.get("token_monthly_limit") or 0),
        input_func,
        output_func,
        allow_zero=True,
    )
    allow_auto_upgrade = _prompt_bool(
        _msg(language, "allow_auto_upgrade"),
        bool(current.get("allow_auto_upgrade", False)),
        input_func,
        output_func,
    )
    default_models = current.get("allowed_models") or [
        "cheap_model",
        "mid_model",
        "strong_model",
        "ollama_local",
        "smart-auto",
    ]
    allowed_models = _prompt_text(
        _msg(language, "allowed_models"),
        ",".join(default_models),
        input_func,
    )

    return {
        "name": current.get("name") or "Default User",
        "api_key": api_key,
        "request_per_minute": request_per_minute,
        "token_daily_limit": daily_limit,
        "token_monthly_limit": monthly_limit,
        "allow_auto_upgrade": allow_auto_upgrade,
        "allowed_models": [item.strip() for item in allowed_models.split(",") if item.strip()],
    }


def _print_review(payload: dict[str, Any], language: str, output_func: OutputFunc) -> None:
    _section(output_func, language, "review_section")
    enabled_models = [
        name for name, model in (payload.get("models") or {}).items() if model.get("enabled")
    ]
    user = payload.get("user") or {}
    output_func(f"Language: {payload.get('language')}")
    output_func(f"Enabled models: {', '.join(enabled_models) if enabled_models else '-'}")
    output_func(f"Default user API Key: {mask_api_key(str(user.get('api_key') or ''))}")
    output_func(f"Allowed models: {', '.join(user.get('allowed_models') or [])}")
    output_func(f"Auto upgrade allowed: {bool(user.get('allow_auto_upgrade'))}")


def _prompt_choice(
    prompt: str,
    choices: list[str],
    default: str,
    input_func: InputFunc,
    output_func: OutputFunc,
) -> str:
    if default not in choices:
        default = choices[0]
    output_func(", ".join(choices))
    while True:
        value = _prompt_text(f"{prompt} [{default}]: ", default, input_func)
        if value in choices:
            return value
        output_func(f"Invalid choice: {value}")


def _prompt_bool(
    prompt: str,
    default: bool,
    input_func: InputFunc,
    output_func: OutputFunc,
) -> bool:
    suffix = "Y/n" if default else "y/N"
    while True:
        value = input_func(f"{prompt} [{suffix}]: ").strip().lower()
        if not value:
            return default
        if value in {"y", "yes", "1", "true", "是", "好"}:
            return True
        if value in {"n", "no", "0", "false", "否", "不"}:
            return False
        output_func("Please enter y or n. / 请输入 y 或 n。")


def _prompt_int(
    prompt: str,
    default: int,
    input_func: InputFunc,
    output_func: OutputFunc,
    *,
    allow_zero: bool,
) -> int:
    while True:
        value = _prompt_text(f"{prompt} [{default}]: ", str(default), input_func)
        parsed = _positive_int(value, default, allow_zero=allow_zero)
        if allow_zero or parsed > 0:
            return parsed
        output_func("Please enter a positive integer. / 请输入正整数。")


def _prompt_text(prompt: str, default: str, input_func: InputFunc) -> str:
    value = input_func(prompt).strip()
    return value if value else default


def _allowed_models(raw_value: Any, data: dict[str, Any]) -> list[str]:
    if isinstance(raw_value, str):
        values = [item.strip() for item in raw_value.split(",") if item.strip()]
    elif isinstance(raw_value, list):
        values = [str(item).strip() for item in raw_value if str(item).strip()]
    else:
        values = []

    valid_models = set((data.get("models") or {}).keys()) | set((data.get("virtual_models") or {}).keys())
    if not values:
        values = [name for name in valid_models if name in {"cheap_model", "mid_model", "strong_model", "smart-auto"}]

    return [name for name in values if name == "*" or name in valid_models]


def _positive_int(value: Any, default: int, *, allow_zero: bool = False) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default

    if parsed < 0 or (parsed == 0 and not allow_zero):
        return default
    return parsed


def _read_config_data(config_path: Path) -> dict[str, Any]:
    with config_path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError(f"Config root must be a JSON object: {config_path}")
    return data


def _normalize_language(language: str) -> str:
    return "zh" if language.lower().startswith("zh") else "en"


def _section(output_func: OutputFunc, language: str, key: str) -> None:
    output_func("")
    output_func("=" * 48)
    output_func(_msg(language, key))
    output_func("=" * 48)


def _line(output_func: OutputFunc, text: str) -> None:
    output_func("")
    output_func(f"-- {text}")


def _say(output_func: OutputFunc, language: str, key: str) -> None:
    output_func(_msg(language, key))


def _msg(language: str, key: str) -> str:
    return MESSAGES.get(language, MESSAGES["en"]).get(key, key)


MESSAGES = {
    "zh": {
        "setup_already_done": "首次运行配置已完成。如需重新配置，请执行：python -m app.setup_wizard --force",
        "start_hint": "现在可以启动服务：python -m uvicorn app.main:app --host 0.0.0.0 --port 8000",
        "welcome": "下面将通过文字提示完成基础配置。直接回车会使用默认值。",
        "models_section": "步骤 1/4：配置真实后端模型",
        "enable_model": "是否启用 {model}",
        "backend_model_name": "后端真实模型名: ",
        "backend_base_url": "OpenAI-compatible Base URL: ",
        "backend_api_key": "后端 API Key，当前 {current}，留空保持不变: ",
        "max_context_tokens": "最大上下文 tokens",
        "empty": "空",
        "no_model_enabled": "提示：当前没有启用真实模型。服务可启动，但 /v1/chat/completions 暂时无法成功转发。",
        "classifier_section": "步骤 2/4：配置轻量分类器（可选）",
        "classifier_enabled": "是否启用分类器",
        "classifier_backend": "选择分类器使用的后端模型",
        "user_section": "步骤 3/4：配置默认用户和权限",
        "user_api_key": "默认用户 API Key: ",
        "request_per_minute": "每分钟请求数，0 表示不限制",
        "daily_limit": "每日 token 限额，0 表示不限制",
        "monthly_limit": "每月 token 限额，0 表示不限制",
        "allow_auto_upgrade": "是否允许校验失败后自动升级模型",
        "allowed_models": "允许模型，逗号分隔: ",
        "review_section": "步骤 4/4：确认并保存",
        "save_confirm": "是否保存以上配置",
        "setup_cancelled": "已取消保存。下次启动仍会进入首次运行文字向导。",
        "saved": "配置已保存到 config.json。",
    },
    "en": {
        "setup_already_done": "First-run setup is already completed. To reconfigure, run: python -m app.setup_wizard --force",
        "start_hint": "You can start the service with: python -m uvicorn app.main:app --host 0.0.0.0 --port 8000",
        "welcome": "This text wizard will guide basic setup. Press Enter to keep the default value.",
        "models_section": "Step 1/4: Configure real backend models",
        "enable_model": "Enable {model}",
        "backend_model_name": "Backend model name: ",
        "backend_base_url": "OpenAI-compatible Base URL: ",
        "backend_api_key": "Backend API Key, current {current}, leave blank to keep it: ",
        "max_context_tokens": "Max context tokens",
        "empty": "empty",
        "no_model_enabled": "Note: no real model is enabled. The service can start, but /v1/chat/completions cannot forward requests yet.",
        "classifier_section": "Step 2/4: Configure lightweight classifier (optional)",
        "classifier_enabled": "Enable classifier",
        "classifier_backend": "Choose classifier backend model",
        "user_section": "Step 3/4: Configure default user and permissions",
        "user_api_key": "Default user API Key: ",
        "request_per_minute": "Requests per minute, 0 means unlimited",
        "daily_limit": "Daily token limit, 0 means unlimited",
        "monthly_limit": "Monthly token limit, 0 means unlimited",
        "allow_auto_upgrade": "Allow auto upgrade after validation failure",
        "allowed_models": "Allowed models, comma-separated: ",
        "review_section": "Step 4/4: Review and save",
        "save_confirm": "Save this configuration",
        "setup_cancelled": "Save cancelled. The first-run text wizard will run again next time.",
        "saved": "Configuration saved to config.json.",
    },
}


def main() -> None:
    parser = argparse.ArgumentParser(description="ModelPilot Gateway first-run text setup wizard")
    parser.add_argument("--force", action="store_true", help="run setup even if it was already completed")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH, help="path to config.json")
    args = parser.parse_args()
    setup_was_needed = args.force or config_needs_setup(args.config)
    try:
        run_text_wizard(config_path=args.config, force=args.force)
    except EOFError:
        print("First-run setup needs terminal input. Please run start_windows.bat from Command Prompt and answer the prompts.")
        raise SystemExit(1) from None
    if setup_was_needed and config_needs_setup(args.config):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
