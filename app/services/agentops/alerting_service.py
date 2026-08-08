from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Literal

from sqlalchemy import and_, func, select

from app.core.config import Settings, get_settings
from app.models.agentops import AlertEvent, LlmCall, ToolCallLog
from app.models.research import ResearchCall
from app.services.agentops.session import agentops_session
from app.services.research_errors import PROVIDER_INFRASTRUCTURE_ERROR_CODES

MetricName = Literal["llm_error_rate", "tool_error_rate", "research_error_rate"]
Severity = Literal["warning"]

TOOL_ERROR_STATUSES = {"error", "persistence_error"}
RESEARCH_INFRASTRUCTURE_ERROR_CODES = PROVIDER_INFRASTRUCTURE_ERROR_CODES


@dataclass(frozen=True)
class ErrorRateEvaluation:
    metric_name: MetricName
    scope: str | None
    window_seconds: int
    threshold: Decimal
    total_count: int
    error_count: int
    observed_value: Decimal | None
    alert_inserted: bool
    severity: Severity | None
    reason: str | None = None


async def evaluate_error_rate(
    *,
    metric_name: MetricName,
    scope: str | None,
    window_seconds: int | None = None,
    threshold: Decimal | None = None,
    settings: Settings | None = None,
    now: datetime | None = None,
) -> ErrorRateEvaluation:
    if metric_name != "research_error_rate" and (window_seconds is None or threshold is None):
        raise ValueError(
            "window_seconds and threshold are required for non-research AgentOps metrics."
        )
    active_settings = settings or get_settings() if window_seconds is None or threshold is None else None
    effective_window_seconds = (
        window_seconds
        if window_seconds is not None
        else active_settings.research_error_alert_window_seconds
    )
    effective_threshold = (
        threshold
        if threshold is not None
        else Decimal(str(active_settings.research_error_alert_threshold))
    )
    evaluated_at = now or datetime.now(UTC)
    window_start = evaluated_at - timedelta(seconds=effective_window_seconds)

    async with agentops_session() as session:
        total_count, error_count = await _count_windowed_calls(
            metric_name=metric_name,
            scope=scope,
            window_start=window_start,
            session=session,
        )

        if total_count == 0:
            return ErrorRateEvaluation(
                metric_name=metric_name,
                scope=scope,
                window_seconds=effective_window_seconds,
                threshold=effective_threshold,
                total_count=0,
                error_count=0,
                observed_value=None,
                alert_inserted=False,
                severity=None,
                reason="not_enough_data",
            )

        observed_value = Decimal(error_count) / Decimal(total_count)
        alert_inserted = observed_value >= effective_threshold
        severity: Severity | None = "warning" if alert_inserted else None

        if alert_inserted:
            session.add(
                AlertEvent(
                    metric_name=metric_name,
                    scope=scope,
                    threshold=effective_threshold,
                    observed_value=observed_value,
                    window_seconds=effective_window_seconds,
                    severity=severity,
                    triggered_at=evaluated_at,
                )
            )
            await session.commit()

        return ErrorRateEvaluation(
            metric_name=metric_name,
            scope=scope,
            window_seconds=effective_window_seconds,
            threshold=effective_threshold,
            total_count=total_count,
            error_count=error_count,
            observed_value=observed_value,
            alert_inserted=alert_inserted,
            severity=severity,
            reason=None,
        )


async def _count_windowed_calls(
    *,
    metric_name: MetricName,
    scope: str | None,
    window_start: datetime,
    session,
) -> tuple[int, int]:
    if metric_name == "llm_error_rate":
        model = LlmCall
        error_filter = LlmCall.status != "success"
    elif metric_name == "tool_error_rate":
        model = ToolCallLog
        error_filter = ToolCallLog.status.in_(TOOL_ERROR_STATUSES)
    elif metric_name == "research_error_rate":
        model = ResearchCall
        error_filter = and_(
            ResearchCall.cache_hit.is_(False),
            ResearchCall.provider_call_made.is_(True),
            ResearchCall.error_code.in_(RESEARCH_INFRASTRUCTURE_ERROR_CODES),
        )
    else:
        raise ValueError(f"Unsupported AgentOps metric '{metric_name}'.")

    filters = [model.created_at >= window_start]
    if scope is not None:
        filters.append(model.stage == scope)

    total_count = await session.scalar(select(func.count()).select_from(model).where(*filters))
    error_count = await session.scalar(
        select(func.count()).select_from(model).where(*filters, error_filter)
    )
    return int(total_count or 0), int(error_count or 0)
