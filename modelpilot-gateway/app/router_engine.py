"""First-layer rule routing for smart-auto requests."""

from dataclasses import dataclass

from fastapi import HTTPException, status

from app import classifier as classifier_module
from app.auth import check_model_permission
from app.schemas import AppConfig, ChatCompletionRequest, ChatMessage, ModelConfig, UserConfig


TIER_ORDER = ["cheap", "mid", "strong"]
TIER_TO_DEFAULT_MODEL = {
    "cheap": "cheap_model",
    "mid": "mid_model",
    "strong": "strong_model",
}


@dataclass(frozen=True)
class RouteDecision:
    """Decision returned by the rule router."""

    routed_model_name: str
    backend_model_name: str
    task_type: str
    route_reason: str
    estimated_tokens: int
    classifier_used: bool = False
    classifier_enabled: bool = False
    classifier_success: bool = False
    classifier_task_type: str | None = None
    classifier_recommended_tier: str | None = None
    classifier_confidence: float | None = None
    fallback_to_rule_route: bool = False
    auto_upgrade_used: bool = False


def detect_task_type(messages: list[ChatMessage]) -> str:
    """Detect a rough task type with keyword rules."""
    text = _messages_to_text(messages).lower()

    if "translate" in text or "翻译" in text:
        return "translation"
    if "summarize" in text or "总结" in text or "摘要" in text:
        return "summary"
    if "rewrite" in text or "改写" in text or "润色" in text:
        return "rewrite"
    if "json" in text or "extract" in text or "提取" in text:
        return "json_extraction"
    if (
        "amazon" in text
        or "walmart" in text
        or "listing" in text
        or "标题" in text
        or "商品描述" in text
    ):
        return "product_copywriting"
    if (
        "code" in text
        or "python" in text
        or "javascript" in text
        or "debug" in text
        or "报错" in text
    ):
        return "code_generation"
    if "strategy" in text or "商业" in text or "战略" in text or "分析" in text:
        return "strategy_analysis"
    if "legal" in text or "contract" in text or "合同" in text or "法务" in text:
        return "legal_or_policy"

    return "unknown"


def estimate_complexity(messages: list[ChatMessage], estimated_tokens: int) -> str:
    """Estimate coarse request complexity."""
    if estimated_tokens >= 8000:
        return "high"
    if estimated_tokens >= 2000:
        return "medium"

    task_type = detect_task_type(messages)
    if task_type in {"code_generation", "strategy_analysis", "legal_or_policy"}:
        return "high"
    if task_type in {"product_copywriting", "json_extraction"}:
        return "medium"

    return "low"


def select_model_by_rules(
    request: ChatCompletionRequest,
    user: UserConfig,
    config: AppConfig,
    estimated_tokens: int,
) -> RouteDecision:
    """Select a real backend model for a smart-auto request."""
    rule_decision = _rule_route_decision(
        request=request,
        user=user,
        config=config,
        estimated_tokens=estimated_tokens,
    )

    if not config.classifier.enabled:
        return rule_decision

    try:
        classification = classifier_module.classify_request(request.messages, config)
    except Exception:
        classification = None

    if classification is None:
        return _copy_decision(
            rule_decision,
            classifier_enabled=True,
            classifier_success=False,
            fallback_to_rule_route=True,
        )

    if classification.confidence < config.classifier.min_confidence:
        return _copy_decision(
            rule_decision,
            classifier_enabled=True,
            classifier_success=True,
            classifier_task_type=classification.task_type,
            classifier_recommended_tier=classification.recommended_tier,
            classifier_confidence=classification.confidence,
            fallback_to_rule_route=True,
        )

    preferred_tier = classification.recommended_tier
    if classification.risk_level == "high":
        preferred_tier = "strong"

    preferred_tier = _upgrade_tier_for_context(
        preferred_tier=preferred_tier,
        config=config,
        estimated_tokens=estimated_tokens,
    )
    routed_model_name = find_allowed_fallback_model(
        user=user,
        config=config,
        preferred_tier=preferred_tier,
    )
    model_config = config.models[routed_model_name]

    return RouteDecision(
        routed_model_name=routed_model_name,
        backend_model_name=model_config.model or routed_model_name,
        task_type=classification.task_type,
        route_reason=_classifier_route_reason(
            classification=classification,
            preferred_tier=preferred_tier,
            routed_model_name=routed_model_name,
            model_config=model_config,
            estimated_tokens=estimated_tokens,
        ),
        estimated_tokens=estimated_tokens,
        classifier_used=True,
        classifier_enabled=True,
        classifier_success=True,
        classifier_task_type=classification.task_type,
        classifier_recommended_tier=classification.recommended_tier,
        classifier_confidence=classification.confidence,
        fallback_to_rule_route=False,
    )


def _rule_route_decision(
    request: ChatCompletionRequest,
    user: UserConfig,
    config: AppConfig,
    estimated_tokens: int,
) -> RouteDecision:
    task_type = detect_task_type(request.messages)
    preferred_tier = _preferred_tier_for_task(task_type, request.messages)
    preferred_tier = _upgrade_tier_for_context(
        preferred_tier=preferred_tier,
        config=config,
        estimated_tokens=estimated_tokens,
    )

    routed_model_name = find_allowed_fallback_model(
        user=user,
        config=config,
        preferred_tier=preferred_tier,
    )
    model_config = config.models[routed_model_name]

    return RouteDecision(
        routed_model_name=routed_model_name,
        backend_model_name=model_config.model or routed_model_name,
        task_type=task_type,
        route_reason=_route_reason(
            task_type=task_type,
            preferred_tier=preferred_tier,
            routed_model_name=routed_model_name,
            model_config=model_config,
            estimated_tokens=estimated_tokens,
        ),
        estimated_tokens=estimated_tokens,
    )


def find_allowed_fallback_model(
    user: UserConfig,
    config: AppConfig,
    preferred_tier: str,
) -> str:
    """Find an enabled allowed model in preferred tier or a higher tier."""
    if preferred_tier not in TIER_ORDER:
        preferred_tier = "mid"

    start_index = TIER_ORDER.index(preferred_tier)
    for tier in TIER_ORDER[start_index:]:
        for model_name, model_config in config.models.items():
            if not model_config.enabled:
                continue
            if _model_tier(model_name, model_config) != tier:
                continue
            if _is_allowed(user, model_name):
                return model_name

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"no enabled allowed model found for tier: {preferred_tier}",
    )


def _preferred_tier_for_task(task_type: str, messages: list[ChatMessage]) -> str:
    if task_type in {"rewrite", "translation", "classification"}:
        return "cheap"
    if task_type == "summary" and _messages_char_count(messages) <= 4000:
        return "cheap"
    if task_type in {"product_copywriting", "customer_support", "json_extraction"}:
        return "mid"
    if task_type in {"code_generation", "strategy_analysis", "legal_or_policy"}:
        return "strong"
    return "mid"


def _upgrade_tier_for_context(
    preferred_tier: str,
    config: AppConfig,
    estimated_tokens: int,
) -> str:
    if preferred_tier == "cheap":
        cheap_limit = _model_limit(config, "cheap_model")
        if cheap_limit and estimated_tokens > cheap_limit:
            preferred_tier = "mid"

    if preferred_tier == "mid":
        mid_limit = _model_limit(config, "mid_model")
        if mid_limit and estimated_tokens > mid_limit:
            preferred_tier = "strong"

    return preferred_tier


def _route_reason(
    task_type: str,
    preferred_tier: str,
    routed_model_name: str,
    model_config: ModelConfig,
    estimated_tokens: int,
) -> str:
    tier = _model_tier(routed_model_name, model_config)
    return (
        f"rule:{task_type};preferred_tier={preferred_tier};"
        f"selected_tier={tier};estimated_tokens={estimated_tokens}"
    )


def _classifier_route_reason(
    classification,
    preferred_tier: str,
    routed_model_name: str,
    model_config: ModelConfig,
    estimated_tokens: int,
) -> str:
    tier = _model_tier(routed_model_name, model_config)
    return (
        f"classifier:{classification.task_type};risk_level={classification.risk_level};"
        f"recommended_tier={classification.recommended_tier};preferred_tier={preferred_tier};"
        f"selected_tier={tier};confidence={classification.confidence:.2f};"
        f"estimated_tokens={estimated_tokens}"
    )


def _copy_decision(decision: RouteDecision, **updates) -> RouteDecision:
    data = {
        "routed_model_name": decision.routed_model_name,
        "backend_model_name": decision.backend_model_name,
        "task_type": decision.task_type,
        "route_reason": decision.route_reason,
        "estimated_tokens": decision.estimated_tokens,
        "classifier_used": decision.classifier_used,
        "classifier_enabled": decision.classifier_enabled,
        "classifier_success": decision.classifier_success,
        "classifier_task_type": decision.classifier_task_type,
        "classifier_recommended_tier": decision.classifier_recommended_tier,
        "classifier_confidence": decision.classifier_confidence,
        "fallback_to_rule_route": decision.fallback_to_rule_route,
        "auto_upgrade_used": decision.auto_upgrade_used,
    }
    data.update(updates)
    return RouteDecision(**data)


def _model_limit(config: AppConfig, model_name: str) -> int | None:
    model_config = config.models.get(model_name)
    if model_config is None:
        return None
    return model_config.max_context_tokens


def _model_tier(model_name: str, model_config: ModelConfig) -> str:
    if model_config.tier in TIER_ORDER:
        return model_config.tier
    if model_name.startswith("cheap"):
        return "cheap"
    if model_name.startswith("mid"):
        return "mid"
    if model_name.startswith("strong"):
        return "strong"
    return "mid"


def _is_allowed(user: UserConfig, model_name: str) -> bool:
    try:
        check_model_permission(user, model_name)
    except HTTPException:
        return False
    return True


def _messages_to_text(messages: list[ChatMessage]) -> str:
    return "\n".join(_content_to_text(message.content) for message in messages)


def _messages_char_count(messages: list[ChatMessage]) -> int:
    return sum(len(_content_to_text(message.content)) for message in messages)


def _content_to_text(content) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    return str(content)
