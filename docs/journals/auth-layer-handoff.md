# Auth-Layer Handoff Note

**Status:** Auth layer complete, verified, and ready for the next phase.
**Repo:** https://github.com/nguyenducviet22/AI-Startup-Coach
**Base context:** Coaching harness merged to `main` at commit `2565661`.

---

## 1. Architecture Overview

```
API routes (app/api/routes.py)
  -> /auth/* routes
      -> AuthService (app/services/auth_service.py)
          -> security primitives (app/core/security.py)
          -> users / auth_credentials / refresh_tokens tables
  -> protected startup routes
      -> get_current_user() / require_startup_owner() dependencies
      -> StartupService / DocumentService / ChatService / StageService
      -> AgentOrchestrator with route-resolved Settings threaded through
```

**Schema:**
- `auth_credentials` stores login-provider credentials separately from `users`.
  - `user_id` references `users.id`.
  - `provider` is present now even though only `password` is supported, so OAuth can be added without reshaping the app identity table.
  - `provider_subject` stores the normalized email for password credentials.
  - `password_hash` is required by a database CHECK constraint when `provider='password'`.
  - Unique constraints enforce one credential per `(user_id, provider)` and one `(provider, provider_subject)`.
- `refresh_tokens` stores only hashed refresh tokens, never raw token values.
  - `token_hash` is unique.
  - `family_id` groups one login session across rotations.
  - `parent_token_id` / `replaced_by_token_id` preserve the rotation chain.
  - `consumed_at`, `revoked_at`, and `reuse_detected_at` model rotation, logout, expiry/revocation, and replay detection.
  - `sequence` is a monotonic identity tie-breaker for deterministic ordering if token issuance history is queried later.

**Layering:**
- `app/core/security.py` owns Argon2id password hash/verify, refresh-token generation/hash, and JWT encode/decode.
- `app/services/auth_service.py` owns signup, login, refresh rotation, reuse detection, and logout business logic.
- `app/api/dependencies.py` owns request authentication and authorization:
  - `get_current_user()` reads `Authorization: Bearer <jwt>`, validates the JWT, and loads the `User`.
  - `require_startup_owner()` loads the startup and returns 404 for both missing and non-owned startup IDs.
- `app/api/routes.py` owns the REST surface:
  - `POST /auth/signup`
  - `POST /auth/login`
  - `POST /auth/refresh`
  - `POST /auth/logout`
  - all seven existing startup-scoped routes now use the shared auth dependencies.

---

## 2. Key Design Decisions

| Decision | Why |
|---|---|
| **DB-backed rotating refresh tokens with reuse detection** | Chosen over stateless-only JWTs because logout and session revocation are required from day one. A replayed consumed token revokes the whole token family, not just the replayed row. |
| **Short-lived stateless access JWTs** | Access tokens stay cheap to validate on each API request. Default TTL is 30 minutes, balancing reduced exposure with avoiding constant refreshes for normal API use. |
| **7-day refresh-token TTL** | Keeps sessions practical for an MVP while still bounding server-side session lifetime. |
| **Argon2id password hashing** | Implemented through `pwdlib[argon2]` / `PasswordHash.recommended()`, wrapped in `app/core/security.py` so the rest of the app does not depend directly on the hashing library. |
| **Credentials separate from users** | `users` remains the app/profile identity table. `auth_credentials` holds provider-specific auth details and includes a `provider` column for future OAuth. |
| **404, not 403, for non-ownership** | Startup-scoped routes keep the existing non-leaking pattern: callers cannot distinguish "does not exist" from "exists but belongs to someone else." |
| **Multiple concurrent sessions allowed** | Each login creates a distinct refresh-token family. Logout revokes only the presented token's current family/session, not every session for the user. |
| **Structured auth errors** | Auth failures use `{"detail": {"field", "code", "message"}}`, matching the recoverable-error style used elsewhere in the coaching harness. |
| **Settings as single source of truth** | `jwt_secret`, `jwt_algorithm`, `access_token_expire_minutes`, and `refresh_token_expire_days` live in `app/core/config.py::Settings` and are mirrored in `.env.example`; auth code does not duplicate hidden fallbacks. |

---

## 3. Known Technical Debt / TODOs

- **No suite-wide `JWT_SECRET` safety net.** There is no `tests/conftest.py` or pytest bootstrap that sets `JWT_SECRET` before any test runs. Tests either construct `Settings(...)` directly or set env/overrides locally. This is a test-suite robustness gap, not a production risk, because production must provide `JWT_SECRET` through real environment config.
- **Refresh tokens are returned in JSON response bodies.** `/auth/login` and `/auth/refresh` include breadcrumb comments noting that the frontend phase must deliberately choose client storage, likely httpOnly cookie vs. JSON-managed storage. Do not let JSON-body refresh tokens become the assumed final browser answer by accident.
- **No "logout everywhere" endpoint.** `POST /auth/logout` revokes only the presented refresh-token family/current session. Global session revocation remains unimplemented by design.
- **`StartupService.create_startup()` still keeps its `UserNotFoundError` check.** Through normal HTTP this is now effectively unreachable because `user_id` comes from a verified token tied to a loaded `User`. It remains harmless defense in depth. Revisit this if a user-delete endpoint is added later, because a theoretical delete between token validation and startup creation would need explicit handling.
- **No rate limiting or login-attempt lockout.** Still out of scope for this backend/auth phase, but important before public exposure.

---

## 4. Pitfalls Observed This Phase

1. **FastAPI dependency overrides do not affect bare cached settings calls.** The chat route had route-level `Depends(get_settings)` overrides in tests, but `build_context_messages()` called the module-level cached `get_settings()` directly, bypassing `app.dependency_overrides`. Once `jwt_secret` became required, that hidden config read could fail on paths that should have used the test override. Future services should receive a `Settings` instance explicitly instead of calling the cached getter internally.
2. **Model/migration constraint drift can silently weaken tests.** The Alembic migration had unique constraints that the ORM model initially lacked, so tests using `Base.metadata.create_all()` did not enforce the same guarantees production had. Keep ORM `__table_args__` in exact sync with migrations, including constraint names, and add direct insert tests for important database constraints.
3. **Concurrency-sensitive auth needs real overlap in tests.** Refresh rotation/reuse detection is covered by a test that holds the relevant row lock, starts two `asyncio.create_task` refresh calls, confirms both are blocked in-flight, then releases the lock. Do not weaken this into sequential awaits.
4. **Config must remain single-source.** `JWT_SECRET` intentionally has no fallback default. If future auth settings are added, define them once in `Settings`, mirror them in `.env.example`, and pass settings through the call graph.
5. **Structured errors are part of the contract.** Auth-service errors are not raw exceptions at the API boundary; they map to stable `field`/`code`/`message` payloads. Frontend work should treat those codes as API contract, not incidental strings.

---

## 5. Touchpoints With the Frontend/UI Phase

- **Token bundle shape:** signup, login, and refresh return `user`, `access_token`, `refresh_token`, `token_type`, and `expires_in`.
- **Authorization header:** all protected API requests must send `Authorization: Bearer <access_token>`.
- **Refresh flow:** when the access token expires, call `POST /auth/refresh` with the refresh token. The old refresh token is consumed and replaced; clients must persist the new refresh token immediately.
- **Logout flow:** call `POST /auth/logout` with the current refresh token. This revokes the current session/family only.
- **Structured errors:** auth failures return `{"detail": {"field", "code", "message"}}`. Codes the UI should be prepared to handle include `email_taken`, `invalid_credentials`, `missing_token`, `invalid_token`, `expired_token`, `refresh_reused`, and `refresh_revoked`.
- **Ownership errors:** startup-scoped non-ownership returns 404, not 403, to avoid leaking whether a startup ID exists.
- **No `user_id` in request bodies:** `POST /startups` derives the user from the access token, and `POST /startups/{id}/chat` no longer accepts `user_id`. The frontend should never send client-chosen `user_id` for these flows.
- **Refresh-token browser storage remains undecided:** decide deliberately during frontend work whether refresh tokens live in httpOnly cookies, memory, or another storage strategy. The backend currently returns them in JSON for backend-only testing convenience.

---

## 6. Current Status

- Auth schema, migration, services, security primitives, REST endpoints, dependencies, and route protection are implemented.
- All seven existing startup routes require authentication; startup-scoped routes enforce ownership through `require_startup_owner()`.
- Access-token validation, refresh rotation, reuse detection, logout revocation, and structured API errors are covered by tests.
- The auth migration is exercised through a real Alembic upgrade test, not only `Base.metadata.create_all()`.
- ORM and migration constraints were reconciled after review, including direct tests for the `auth_credentials` unique constraints and password-hash CHECK constraint.
- Full regression suite is green: 132 tests passed.
- `.env` remains ignored; `.env.example` documents the required auth settings.
