"""Backend clients for OpenAI-compatible providers."""

from typing import Any

import httpx

from app.schemas import ModelConfig


class BackendClientError(RuntimeError):
    """Raised when a backend request fails."""


class OpenAICompatibleClient:
    """Minimal client for OpenAI-compatible chat completions APIs."""

    def __init__(self, timeout_seconds: float = 60.0) -> None:
        self.timeout_seconds = timeout_seconds

    async def chat_completions(
        self,
        request_payload: dict[str, Any],
        model_config: ModelConfig,
    ) -> dict[str, Any]:
        """Forward a chat completions request to an OpenAI-compatible backend."""
        url = self._chat_completions_url(model_config)
        payload = dict(request_payload)
        backend_model = model_config.model or payload.get("model")
        if backend_model:
            payload["model"] = backend_model

        timeout = self._timeout(model_config)
        headers = {"Content-Type": "application/json"}
        if model_config.api_key:
            headers["Authorization"] = f"Bearer {model_config.api_key}"

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise BackendClientError(
                f"Backend returned HTTP {exc.response.status_code}"
            ) from exc
        except httpx.RequestError as exc:
            raise BackendClientError("Backend request failed") from exc

        try:
            response_data = response.json()
        except ValueError as exc:
            raise BackendClientError("Backend returned non-JSON response") from exc

        if not isinstance(response_data, dict):
            raise BackendClientError("Backend response root must be a JSON object")

        return response_data

    def _chat_completions_url(self, model_config: ModelConfig) -> str:
        base_url = (model_config.base_url or "").strip().rstrip("/")
        if not base_url:
            raise BackendClientError("Backend base_url is not configured")

        if base_url.endswith("/chat/completions"):
            return base_url

        return f"{base_url}/chat/completions"

    def _timeout(self, model_config: ModelConfig) -> httpx.Timeout:
        timeout_value = 60.0
        if model_config.model_extra:
            timeout_value = float(model_config.model_extra.get("timeout_seconds", 60.0))
        return httpx.Timeout(timeout_value)
