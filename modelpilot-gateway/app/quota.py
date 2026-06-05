"""In-memory quota management for ModelPilot Gateway."""

import time
from collections import defaultdict, deque
from datetime import datetime
from typing import Any

from app.schemas import ChatMessage


class InMemoryQuotaManager:
    """Simple in-memory rate and token quota tracker."""

    def __init__(self) -> None:
        self._request_timestamps: dict[str, deque[float]] = defaultdict(deque)
        self._daily_tokens: dict[tuple[str, str], int] = defaultdict(int)
        self._monthly_tokens: dict[tuple[str, str], int] = defaultdict(int)

    def check_rate_limit(self, user_name: str, request_per_minute: int | None) -> bool:
        """Return False when the user has exceeded request_per_minute."""
        if not request_per_minute or request_per_minute <= 0:
            return True

        now = time.time()
        timestamps = self._request_timestamps[user_name]
        while timestamps and now - timestamps[0] >= 60:
            timestamps.popleft()

        if len(timestamps) >= request_per_minute:
            return False

        timestamps.append(now)
        return True

    def estimate_tokens_from_messages(self, messages: list[ChatMessage]) -> int:
        """Estimate prompt tokens from chat messages without tokenizer dependency."""
        total_chars = 0
        for message in messages:
            total_chars += len(message.role or "")
            total_chars += len(_content_to_text(message.content))
            if message.name:
                total_chars += len(message.name)

        return max(1, total_chars // 4)

    def check_token_quota(
        self,
        user_name: str,
        estimated_tokens: int,
        daily_limit: int | None,
        monthly_limit: int | None,
    ) -> bool:
        """Return False when estimated tokens would exceed daily or monthly quota."""
        day_key = (user_name, datetime.now().strftime("%Y%m%d"))
        month_key = (user_name, datetime.now().strftime("%Y%m"))

        if daily_limit and daily_limit > 0:
            if self._daily_tokens[day_key] + estimated_tokens > daily_limit:
                return False

        if monthly_limit and monthly_limit > 0:
            if self._monthly_tokens[month_key] + estimated_tokens > monthly_limit:
                return False

        return True

    def record_token_usage(
        self,
        user_name: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> None:
        """Record prompt and completion tokens for daily and monthly limits."""
        token_count = max(0, prompt_tokens) + max(0, completion_tokens)
        day_key = (user_name, datetime.now().strftime("%Y%m%d"))
        month_key = (user_name, datetime.now().strftime("%Y%m"))

        self._daily_tokens[day_key] += token_count
        self._monthly_tokens[month_key] += token_count


def _content_to_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    return str(content)
