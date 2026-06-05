"""Authentication and basic authorization helpers."""

import hmac
from datetime import datetime

from fastapi import HTTPException, Request, status

from app.schemas import AppConfig, UserConfig
from app.utils import mask_api_key


def get_api_key_from_request(request: Request) -> str | None:
    """Extract an API key from Authorization Bearer or x-api-key headers."""
    authorization = request.headers.get("authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() == "bearer" and token.strip():
        return token.strip()

    api_key = request.headers.get("x-api-key")
    if api_key and api_key.strip():
        return api_key.strip()

    return None


def authenticate_user(request: Request, config: AppConfig) -> tuple[str, UserConfig]:
    """Authenticate a request and return the matched user id and config."""
    api_key = get_api_key_from_request(request)
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing api key",
        )

    for user_id, user in config.users.items():
        if hmac.compare_digest(api_key, user.api_key):
            if not user.enabled:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="user is disabled",
                )
            return user_id, user

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=f"invalid api key: {mask_api_key(api_key)}",
    )


def check_ip_permission(user: UserConfig, request: Request, config: AppConfig) -> None:
    """Check user IP allowlist and denylist permissions."""
    client_ip = _get_client_ip(request, config)

    if client_ip in user.ip_denylist:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="ip is denied",
        )

    if user.ip_allowlist and "*" not in user.ip_allowlist:
        if client_ip not in user.ip_allowlist:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="ip is not allowed",
            )


def check_allowed_hours(user: UserConfig) -> None:
    """Check whether the current local hour is allowed for the user."""
    if not user.allowed_hours:
        return

    current_hour = datetime.now().hour
    if current_hour not in user.allowed_hours:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="current hour is not allowed",
        )


def check_model_permission(user: UserConfig, model_name: str) -> None:
    """Check whether a user is allowed to access a requested model."""
    if "*" in user.allowed_models:
        return

    if model_name not in user.allowed_models:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"model is not allowed: {model_name}",
        )


def _get_client_ip(request: Request, config: AppConfig) -> str:
    if config.server.trust_proxy_headers:
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",", 1)[0].strip()

    if request.client:
        return request.client.host

    return ""
