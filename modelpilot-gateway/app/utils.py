"""General utility helpers for ModelPilot Gateway."""


def mask_api_key(key: str) -> str:
    """Mask an API key while keeping a small recognizable prefix and suffix."""
    if not key:
        return ""

    key = str(key)
    if len(key) <= 8:
        if len(key) <= 2:
            return "*" * len(key)
        return f"{key[0]}...{key[-1]}"

    return f"{key[:4]}...{key[-4:]}"
