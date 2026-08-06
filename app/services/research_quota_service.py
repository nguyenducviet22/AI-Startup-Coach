"""Correctness-critical, transaction-locked research quota reservations."""

import hashlib
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.research import ResearchQuotaReservation
from app.services.research_errors import ResearchErrorDetail, ResearchServiceError


class ResearchQuotaService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings

    async def reserve(
        self,
        *,
        user_id: UUID,
        session_id: UUID | None,
        credits: int,
        now: datetime | None = None,
    ) -> ResearchQuotaReservation:
        current = now or datetime.now(UTC)
        await self._lock_owner_ids(user_id, session_id)
        if session_id is not None:
            await self._check_scope(
                scope="session",
                scope_id=session_id,
                call_limit=self.settings.research_session_hourly_call_limit,
                credit_limit=self.settings.research_session_daily_credit_limit,
                requested_credits=credits,
                current=current,
            )
        await self._check_scope(
            scope="user",
            scope_id=user_id,
            call_limit=self.settings.research_user_hourly_call_limit,
            credit_limit=self.settings.research_user_daily_credit_limit,
            requested_credits=credits,
            current=current,
        )
        reservation = ResearchQuotaReservation(
            user_id=user_id,
            session_id=session_id,
            reserved_calls=1,
            reserved_credits=credits,
            status="reserved",
        )
        self.session.add(reservation)
        await self.session.commit()
        await self.session.refresh(reservation)
        return reservation

    async def reconcile(
        self,
        *,
        reservation: ResearchQuotaReservation,
        credits_charged: int | None,
        provider_succeeded: bool,
    ) -> None:
        if provider_succeeded:
            reservation.charged_credits = (
                reservation.reserved_credits if credits_charged is None else credits_charged
            )
            reservation.status = "charged"
            reservation.reconciled_at = datetime.now(UTC)
        else:
            reservation.released_credits = reservation.reserved_credits
            reservation.status = "released"
            reservation.released_at = datetime.now(UTC)
        await self.session.commit()

    async def _lock_owner_ids(self, user_id: UUID, session_id: UUID | None) -> None:
        keys = sorted(_advisory_key(value) for value in (user_id, session_id) if value is not None)
        for key in keys:
            await self.session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})

    async def _check_scope(
        self,
        *,
        scope: str,
        scope_id: UUID,
        call_limit: int,
        credit_limit: int,
        requested_credits: int,
        current: datetime,
    ) -> None:
        column = ResearchQuotaReservation.session_id if scope == "session" else ResearchQuotaReservation.user_id
        active = ResearchQuotaReservation.status.in_(("reserved", "charged"))
        call_start = current - timedelta(hours=1)
        credits_start = current - timedelta(hours=24)
        calls = await self.session.scalar(
            select(func.coalesce(func.sum(ResearchQuotaReservation.reserved_calls), 0)).where(
                column == scope_id, active, ResearchQuotaReservation.created_at >= call_start
            )
        )
        if int(calls or 0) >= call_limit:
            raise await self._rate_limit_error(scope, call_limit, column, scope_id, call_start)
        credits = await self.session.scalar(
            select(
                func.coalesce(
                    func.sum(
                        func.coalesce(
                            ResearchQuotaReservation.charged_credits,
                            ResearchQuotaReservation.reserved_credits,
                        )
                    ),
                    0,
                )
            ).where(column == scope_id, active, ResearchQuotaReservation.created_at >= credits_start)
        )
        if int(credits or 0) + requested_credits > credit_limit:
            raise await self._rate_limit_error(
                scope, credit_limit, column, scope_id, credits_start, timedelta(hours=24)
            )

    async def _rate_limit_error(
        self,
        scope: str,
        limit: int,
        column,
        scope_id: UUID,
        window_start: datetime,
        window: timedelta = timedelta(hours=1),
    ) -> ResearchServiceError:
        first = await self.session.scalar(
            select(func.min(ResearchQuotaReservation.created_at)).where(
                column == scope_id,
                ResearchQuotaReservation.status.in_(("reserved", "charged")),
                ResearchQuotaReservation.created_at >= window_start,
            )
        )
        retry_at = (first or datetime.now(UTC)) + window
        return ResearchServiceError(
            ResearchErrorDetail(
                field="research",
                code="research_rate_limited",
                message="Research quota has been reached.",
                scope=scope,
                limit=limit,
                retry_at=retry_at,
            )
        )


def _advisory_key(value: UUID) -> int:
    return int.from_bytes(hashlib.sha256(value.bytes).digest()[:8], "big", signed=True)
