from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Literal

from sqlalchemy import func, select

from app.models.agentops import AlertEvent, LlmCall, ToolCallLog
from app.services.agentops.session import agentops_session

MetricName = Literal["llm_error_rate", "tool_error_rate"]
Severity = Literal["warning"]

TOOL_ERROR_STATUSES = {"error", "persistence_error"}


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
    window_seconds: int,
    threshold: Decimal,
    now: datetime | None = None,
) -> ErrorRateEvaluation:
    evaluated_at = now or datetime.now(UTC)
    window_start = evaluated_at - timedelta(seconds=window_seconds)

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
                window_seconds=window_seconds,
                threshold=threshold,
                total_count=0,
                error_count=0,
                observed_value=None,
                alert_inserted=False,
                severity=None,
                reason="not_enough_data",
            )

        observed_value = Decimal(error_count) / Decimal(total_count)
        alert_inserted = observed_value >= threshold
        severity: Severity | None = "warning" if alert_inserted else None

        if alert_inserted:
            session.add(
                AlertEvent(
                    metric_name=metric_name,
                    scope=scope,
                    threshold=threshold,
                    observed_value=observed_value,
                    window_seconds=window_seconds,
                    severity=severity,
                    triggered_at=evaluated_at,
                )
            )
            await session.commit()

        return ErrorRateEvaluation(
            metric_name=metric_name,
            scope=scope,
            window_seconds=window_seconds,
            threshold=threshold,
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
