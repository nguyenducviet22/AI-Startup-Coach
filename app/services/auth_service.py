import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import Select, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.models.auth import AuthCredential, RefreshToken
from app.models.user import User


@dataclass(frozen=True)
class AuthErrorDetail:
    field: str | None
    code: str
    message: str

    def to_dict(self) -> dict[str, str | None]:
        return {
            "field": self.field,
            "code": self.code,
            "message": self.message,
        }


class AuthServiceError(Exception):
    def __init__(self, *, field: str | None, code: str, message: str) -> None:
        super().__init__(message)
        self.detail = AuthErrorDetail(field=field, code=code, message=message)


class AuthService:
    def __init__(self, session: AsyncSession, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()

    async def signup(self, *, name: str, email: str, password: str) -> dict[str, Any]:
        normalized_email = _normalize_email(email)
        existing = await self.session.scalar(
            select(User.id)
            .join(AuthCredential, AuthCredential.user_id == User.id, isouter=True)
            .where(
                (User.email == normalized_email)
                | (
                    (AuthCredential.provider == "password")
                    & (AuthCredential.provider_subject == normalized_email)
                )
            )
        )
        if existing is not None:
            raise _email_taken()

        try:
            user = User(name=name, email=normalized_email)
            self.session.add(user)
            await self.session.flush()

            credential = AuthCredential(
                user_id=user.id,
                provider="password",
                provider_subject=normalized_email,
                password_hash=hash_password(password),
            )
            self.session.add(credential)
            await self.session.flush()

            result = await self._issue_token_pair(user=user, credential_id=credential.id)
            await self.session.commit()
            return result
        except IntegrityError as exc:
            await self.session.rollback()
            raise _email_taken() from exc

    async def login(self, *, email: str, password: str) -> dict[str, Any]:
        normalized_email = _normalize_email(email)
        result = await self.session.execute(
            select(User, AuthCredential)
            .join(AuthCredential, AuthCredential.user_id == User.id)
            .where(
                AuthCredential.provider == "password",
                AuthCredential.provider_subject == normalized_email,
            )
        )
        row = result.one_or_none()
        if row is None:
            raise _invalid_credentials()

        user, credential = row
        if credential.password_hash is None or not verify_password(password, credential.password_hash):
            raise _invalid_credentials()

        auth_result = await self._issue_token_pair(user=user, credential_id=credential.id)
        await self.session.commit()
        return auth_result

    async def refresh(self, refresh_token: str | None) -> dict[str, Any]:
        token = await self._get_refresh_token_for_update(refresh_token)
        now = datetime.now(UTC)

        if token.consumed_at is not None:
            await self._mark_family_compromised(token, now=now)
            await self.session.commit()
            raise _refresh_reused()
        if token.revoked_at is not None:
            raise _refresh_revoked()
        if token.expires_at <= now:
            token.revoked_at = now
            await self.session.commit()
            raise _expired_token()

        user = await self.session.get(User, token.user_id)
        if user is None:
            raise _invalid_token()

        token.consumed_at = now
        raw_refresh_token = generate_refresh_token()
        replacement = RefreshToken(
            family_id=token.family_id,
            user_id=token.user_id,
            credential_id=token.credential_id,
            token_hash=hash_refresh_token(raw_refresh_token),
            parent_token_id=token.id,
            expires_at=now + timedelta(days=self.settings.refresh_token_expire_days),
        )
        self.session.add(replacement)
        await self.session.flush()
        token.replaced_by_token_id = replacement.id

        await self.session.commit()
        return self._build_auth_result(user=user, refresh_token=raw_refresh_token)

    async def logout(self, refresh_token: str | None) -> dict[str, bool]:
        token = await self._get_refresh_token_for_update(refresh_token)
        now = datetime.now(UTC)

        if token.consumed_at is not None:
            # A rotated token presented to logout is indistinguishable from replay, so treat it as compromised.
            await self._mark_family_compromised(token, now=now)
            await self.session.commit()
            raise _refresh_reused()
        if token.revoked_at is not None:
            raise _refresh_revoked()
        if token.expires_at <= now:
            token.revoked_at = now
            await self.session.commit()
            raise _expired_token()

        await self._revoke_family(token.family_id, now=now)
        await self.session.commit()
        return {"revoked": True}

    async def _issue_token_pair(self, *, user: User, credential_id: uuid.UUID | None) -> dict[str, Any]:
        raw_refresh_token = generate_refresh_token()
        refresh_token = RefreshToken(
            family_id=uuid.uuid4(),
            user_id=user.id,
            credential_id=credential_id,
            token_hash=hash_refresh_token(raw_refresh_token),
            expires_at=datetime.now(UTC) + timedelta(days=self.settings.refresh_token_expire_days),
        )
        self.session.add(refresh_token)
        await self.session.flush()
        return self._build_auth_result(user=user, refresh_token=raw_refresh_token)

    async def _get_refresh_token_for_update(self, refresh_token: str | None) -> RefreshToken:
        if refresh_token is None or refresh_token.strip() == "":
            raise _missing_token()

        statement: Select[tuple[RefreshToken]] = (
            select(RefreshToken)
            .where(RefreshToken.token_hash == hash_refresh_token(refresh_token))
            .with_for_update()
        )
        result = await self.session.execute(statement)
        token = result.scalar_one_or_none()
        if token is None:
            raise _invalid_token()
        return token

    async def _mark_family_compromised(self, token: RefreshToken, *, now: datetime) -> None:
        token.reuse_detected_at = now
        await self._revoke_family(token.family_id, now=now)

    async def _revoke_family(self, family_id: uuid.UUID, *, now: datetime) -> None:
        await self.session.execute(
            update(RefreshToken)
            .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=now)
        )

    def _build_auth_result(self, *, user: User, refresh_token: str) -> dict[str, Any]:
        return {
            "user": _user_to_dict(user),
            "access_token": create_access_token(user.id, settings=self.settings),
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": self.settings.access_token_expire_minutes * 60,
        }


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _user_to_dict(user: User) -> dict[str, str]:
    return {
        "id": str(user.id),
        "name": user.name,
        "email": user.email,
    }


def _email_taken() -> AuthServiceError:
    return AuthServiceError(
        field="email",
        code="email_taken",
        message="Email is already registered.",
    )


def _invalid_credentials() -> AuthServiceError:
    return AuthServiceError(
        field=None,
        code="invalid_credentials",
        message="Email or password is incorrect.",
    )


def _missing_token() -> AuthServiceError:
    return AuthServiceError(
        field="refresh_token",
        code="missing_token",
        message="Refresh token is required.",
    )


def _invalid_token() -> AuthServiceError:
    return AuthServiceError(
        field="refresh_token",
        code="invalid_token",
        message="Refresh token is invalid.",
    )


def _expired_token() -> AuthServiceError:
    return AuthServiceError(
        field="refresh_token",
        code="expired_token",
        message="Refresh token has expired.",
    )


def _refresh_reused() -> AuthServiceError:
    return AuthServiceError(
        field="refresh_token",
        code="refresh_reused",
        message="Refresh token reuse was detected.",
    )


def _refresh_revoked() -> AuthServiceError:
    return AuthServiceError(
        field="refresh_token",
        code="refresh_revoked",
        message="Refresh token has been revoked.",
    )
