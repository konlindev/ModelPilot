# Configuration Schema / 配置字段说明

This document describes the main fields in `config.json`.

本文说明 `config.json` 的主要字段。

## setup

First-run text wizard state.

首次运行文字向导状态。

- `completed`: Whether the first-run text wizard has been completed. If `false`, startup scripts run `python -m app.setup_wizard` before starting the service.
- `language`: Language chosen in the wizard. Supported values: `zh`, `en`.
- `completed_at`: Local timestamp when setup was saved.

To re-run setup:

```bash
python -m app.setup_wizard --force
```

## github

Startup-time GitHub update check configuration.

启动脚本中的 GitHub 自动更新检测配置。

- `update_check_enabled`: Whether startup scripts should check GitHub before running the service.
- `remote`: Git remote name. Default: `origin`.
- `branch`: Remote branch to track. Default: `main`.
- `repo_url`: Repository URL for documentation and operator reference.
- `token`: Optional GitHub token. Public repositories can leave this empty. Private repositories should set a Personal Access Token here.
- `protect_config`: Whether to preserve local config files during auto update.
- `protected_paths`: Paths that must be restored after pulling updates. Default: `["modelpilot-gateway/config.json"]`.

When updates are pulled, `config.json` is restored to the local version so local API keys, user settings, and backend model settings are not overwritten.

## server

- `host`: Service host used for local display and startup messages. Example: `127.0.0.1`.
- `port`: Service port. Example: `8000`.
- `language`: Startup message language. Supports `zh`, `zh-CN`, and `en`.
- `log_level`: Python logging level, such as `INFO`, `DEBUG`, `WARNING`, `ERROR`.
- `trust_proxy_headers`: Whether to trust `X-Forwarded-For`. Default is `false`. When true, the first IP in `X-Forwarded-For` is used for IP permission checks.

## models

Real backend model definitions. Keys such as `cheap_model`, `mid_model`, and `strong_model` are gateway model names.

- `enabled`: Whether this backend model can be used.
- `provider`: Provider label, for example `openai`, `ollama`, or another OpenAI-compatible provider.
- `tier`: Routing tier. Supported values: `cheap`, `mid`, `strong`.
- `max_context_tokens`: Approximate context limit used by `smart-auto`.
- `model`: Backend model name sent to the provider, for example `gpt-4o-mini`.
- `base_url`: OpenAI-compatible base URL. If it ends with `/v1`, requests go to `/v1/chat/completions`.
- `api_key`: Backend API key. Leave empty for local providers that do not require one.
- `timeout_seconds`: Optional per-model timeout for backend requests.

## virtual_models

Virtual model definitions. The default virtual model is `smart-auto`.

- `enabled`: Whether the virtual model appears in `/v1/models`.
- `strategy`: Human-readable strategy label, such as `rules-with-classifier-validation`.
- `description`: Optional description.
- `candidate_models`: Real model names that the virtual model may route to.

## classifier

Optional lightweight classifier configuration.

- `enabled`: Whether classifier-assisted routing is enabled.
- `backend_model`: A model key from `models`, such as `ollama_local`.
- `timeout_seconds`: Classifier request timeout.
- `min_confidence`: Minimum confidence required before classifier advice affects routing.
- `default_virtual_model`: Usually `smart-auto`.

The classifier must return strict JSON with fields: `task_type`, `risk_level`, `complexity`, `needs_json`, `recommended_tier`, and `confidence`.

## validation

Response validation and auto-upgrade configuration.

- `enabled`: Whether response validation is enabled.
- `auto_upgrade_enabled`: Whether validation failures may trigger model upgrade.
- `apply_to_direct_model`: Whether direct real-model requests are validated. Default is `false`.
- `min_response_chars`: Minimum allowed response content length.
- `banned_words`: Words that fail validation when present in output.
- `competitor_brand_words`: Competitor brand words that fail validation when present in output.
- `max_prompt_chars`: Reserved validation limit for prompt length.

Validation can fail on empty response, missing choices, empty content, too-short content, invalid JSON mode output, banned words, competitor brand words, backend rate limit errors, and backend context length errors.

## users

User API key and permission configuration. The key under `users`, such as `default_user`, is the stable internal user id.

- `enabled`: Whether the user can authenticate.
- `name`: Display name.
- `api_key`: User API key for `Authorization: Bearer ...` or `x-api-key`.
- `ip_allowlist`: Optional allowlist. Empty means any IP not denied is allowed.
- `ip_denylist`: IPs that are always denied.
- `token_daily_limit`: Daily token limit. `0` means unlimited.
- `token_monthly_limit`: Monthly token limit. `0` means unlimited.
- `request_per_minute`: Per-user request rate limit.
- `allowed_hours`: List of allowed local hours, from `0` to `23`.
- `allowed_models`: Models this user can access, such as `smart-auto`, `cheap_model`, `mid_model`, `strong_model`.
- `allowed_task_types`: Reserved list of task types.
- `allow_stream`: Reserved streaming permission. Streaming is not implemented yet.
- `allow_auto_upgrade`: Whether validation failure can upgrade this user's request to a higher tier.

## allowed_hours

`allowed_hours` uses local server time. Example:

```json
"allowed_hours": [9, 10, 11, 12, 13, 14, 15, 16, 17]
```

The user can call APIs only during these hours.

## allowed_models

Use this to restrict access by gateway model name:

```json
"allowed_models": ["smart-auto", "cheap_model"]
```

For auto-upgrade to work, the user must also be allowed to use the target higher-tier model.

## quotas

Current quota fields live under each user:

- `request_per_minute`: In-memory request rate limit.
- `token_daily_limit`: In-memory daily token limit.
- `token_monthly_limit`: In-memory monthly token limit.

These counters reset when the process restarts. Redis or database persistence is planned for a later phase.

## trust_proxy_headers

When `server.trust_proxy_headers=false`, IP permission checks use `request.client.host`.

When `server.trust_proxy_headers=true`, IP permission checks use the first IP from `X-Forwarded-For`. Enable this only behind a trusted reverse proxy.
