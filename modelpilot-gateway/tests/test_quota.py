from app.quota import InMemoryQuotaManager
from app.schemas import ChatMessage


def test_rate_limit_blocks_requests_over_limit() -> None:
    quota = InMemoryQuotaManager()

    assert quota.check_rate_limit("user-a", 1) is True
    assert quota.check_rate_limit("user-a", 1) is False


def test_token_quota_blocks_when_estimate_exceeds_limit() -> None:
    quota = InMemoryQuotaManager()

    assert quota.check_token_quota("user-a", 5, daily_limit=4, monthly_limit=0) is False
    assert quota.check_token_quota("user-a", 5, daily_limit=5, monthly_limit=5) is True


def test_record_token_usage_counts_prompt_and_completion_tokens() -> None:
    quota = InMemoryQuotaManager()

    quota.record_token_usage("user-a", prompt_tokens=4, completion_tokens=3)

    assert quota.check_token_quota("user-a", 1, daily_limit=7, monthly_limit=0) is False
    assert quota.check_token_quota("user-a", 1, daily_limit=8, monthly_limit=0) is True


def test_estimate_tokens_from_messages_is_safe() -> None:
    quota = InMemoryQuotaManager()

    estimated_tokens = quota.estimate_tokens_from_messages(
        [ChatMessage(role="user", content="hello world")]
    )

    assert estimated_tokens >= 1
