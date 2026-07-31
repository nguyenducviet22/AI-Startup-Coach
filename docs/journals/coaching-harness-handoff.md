# Coaching-Harness Handoff Note

**Status:** Backend complete, committed, pushed to `main`.
**Commit:** `2565661` — "Initial coaching-harness backend implementation"
**Repo:** https://github.com/nguyenducviet22/AI-Startup-Coach
**Full spec:** `docs/coaching-harness-spec-en.md`

---

## 1. Architecture Overview

```
API routes (app/api/routes.py)
  → StartupService / StageService / DocumentService / ChatService (DB-backed)
  → AgentOrchestrator (app/services/orchestrator.py)
      → context_builder.py     — builds system prompt + truncated history
      → SkillLoader             — loads skills/{stage}.md dynamically
      → stage_tools.py          — filters tools exposed to current stage
      → ToolDispatcher          — validates + persists tool calls
      → OpenRouterChatClient    — LLM I/O, retry/backoff
```

**Key modules:**
- `app/domain/stages.py` — canonical `StageName` enum, pure `get_next_stage()`, `validate_stage()`. No side effects.
- `app/services/skill_loader.py` — loads `skills/{stage}.md` at runtime, anchored to `ROOT_DIR` (not cwd). Raises `SkillNotFoundError`. `completed` stage uses a built-in prompt, no file.
- `app/services/context_builder.py` — assembles system prompt (base rules + skill + current document) + truncates history to `CHAT_HISTORY_LIMIT`, oldest-first drop, system prompt always preserved.
- `app/services/stage_tools.py` — `STAGE_TOOL_NAMES` dict maps each stage to its exact allowed tool set. `idea` → readiness only; document stages → `generate_*` + readiness; `completed` → none.
- `app/tools/schemas.py` / `validation.py` — Pydantic models per tool; `validate_tool_arguments()` returns structured `{"ok": bool, ...}` payloads, never raises to the caller.
- `app/services/tool_dispatcher.py` — enforces stage-tool gating, runs validation, persists via `DocumentService` when injected (else `persistence.status="deferred"`). `check_stage_readiness` is structurally excluded from persistence (not in `TOOL_DOCUMENT_TYPES`).
- `app/services/orchestrator.py` — `AgentOrchestrator.handle_turn()` runs the full loop: build context → call LLM → dispatch any `tool_calls` (supports multiple per turn, in order) → feed results back → final LLM call → return `OrchestratorResult` (content + tool audit data).
- `app/llm/openrouter.py` — `OpenRouterChatClient` behind a `ChatCompletionClient` protocol. Uses OpenAI SDK pointed at OpenRouter (`base_url`, `OPENROUTER_API_KEY`). Retries `APITimeoutError`/`APIConnectionError`/`RateLimitError` and transient `APIStatusError` (408/409/429/5xx) with exponential backoff; non-transient status errors (e.g. 401/400) raise immediately, no retry.
- `app/services/document_service.py` — versioned writes (mark old row `is_current=false`, insert `version+1`) for all 6 document tables, atomic per write via row-level locking (`SELECT ... FOR UPDATE` on the parent `startups` row first, then the current document row — parent lock is what protects the first-write case).
- `app/services/chat_service.py` — session reuse (explicit `session_id`, latest-session fallback, or create), message persistence, `get_recent_messages()` filters to `role IN ('user','assistant')` at the SQL level (tool messages are audit-only, never replayed to the LLM as standalone messages — OpenAI's API requires `tool` messages to immediately follow the `assistant` message with matching `tool_calls`, so replaying them out of that structure would break the API contract).
- `app/services/stage_service.py` — `advance_stage()` (exactly one step via `get_next_stage()`) and `set_stage()` (manual override/backtrack). **Neither is ever called by the orchestrator or readiness logic — only the REST endpoints call these.**

**DB:** PostgreSQL, SQLAlchemy async, Alembic migrations. 10 tables per spec section 4, plus a `sequence` identity column added to `chat_sessions`/`chat_messages` (see §2).

---

## 2. Key Design Decisions

| Decision | Why |
|---|---|
| **OpenRouter instead of direct OpenAI** | User preference/cost flexibility across providers. Client wrapper isolates the SDK behind a `ChatCompletionClient` protocol — orchestrator code has zero OpenAI-SDK imports, so swapping providers later doesn't touch business logic. |
| **Agent never auto-advances stage** | Educational product — students should consciously confirm moving to the next framework, not have it happen silently. `check_stage_readiness` is validation-only; DB stage mutation happens exclusively through `POST /advance-stage` / `PATCH /stage`. This is enforced structurally (readiness tool is excluded from `TOOL_DOCUMENT_TYPES`, so it can never trigger a persistence write), not just by convention. |
| **Tool access restricted per stage** | Prevents the LLM from calling `generate_bmc` while still in `idea`, which would produce nonsensical/premature output. Enforced via `get_tool_names_for_stage()` + `ToolDispatcher` rejection (`tool_not_available_for_stage` structured error) — tested with exact-tuple assertions to catch any leakage. |
| **Skill content loaded from disk, not hardcoded** | Lets skill content (coaching methodology per stage) be edited without touching orchestrator code or redeploying logic changes. |
| **Versioned document writes (never UPDATE in place)** | Preserves the student's idea evolution history — pedagogically useful, and required by spec. Protected by transactional row-locking to prevent race conditions on concurrent writes to the same startup. |
| **Tool validation errors return structured, recoverable payloads (never raise/crash)** | Lets the LLM see exactly what was wrong (`field`, `code`, `message`) and self-correct on the next turn, instead of the conversation dying on a schema mismatch. |
| **`sequence` identity column added to chat tables** | `created_at` alone isn't a safe sort key — two rows can share a timestamp (microsecond collisions are rare but not impossible), which would scramble conversation order fed to the LLM. `sequence` is a monotonic tie-breaker. |
| **Persistence deferred/mockable in the orchestrator/dispatcher** | Let Phase 4 (orchestrator logic) be fully tested with zero DB and zero network calls, isolating LLM-loop bugs from persistence bugs. `ToolDispatcher(document_service=None)` still works standalone. |

---

## 3. Known Technical Debt / TODOs

- **No real authentication.** `user_id` is accepted directly in request bodies with no verification the caller *is* that user. This is the explicit scope of the next phase.
- **No AgentOps.** No logging/tracing of LLM calls, no cost tracking, no eval harness. Out of scope per spec §10.
- **No frontend.** Backend-only, verified via REST calls (curl/tests), never through a UI.
- **`get_previous_stage()` does not exist** — only `get_next_stage()`. `PATCH /stage` validates against the stage enum but doesn't compute "the stage before X"; it accepts any valid target stage directly. This was a deliberate choice, not an oversight, but worth knowing if you build UI affordances like a "back" button that assumes a `get_previous_stage()` helper exists.
- **Model name (`OPENROUTER_MODEL`) is a config placeholder** — never hardcoded to a verified-real OpenRouter model slug in code; whoever runs this needs to confirm/set a real model string via env var.
- **The initial schema migration's backfill pattern was never tested against pre-existing data** (only the later `chat_sequence_ordering` migration needed backfill logic, and that one *was* tested with tie-forcing test cases). Flagged as a practice to keep enforcing going forward: any future migration with backfill logic needs a test that seeds rows first, then runs the actual `alembic upgrade`, not just `Base.metadata.create_all()`.
- **No rate limiting / abuse protection** on any endpoint — reasonable for MVP scope, but relevant once real users exist.

---

## 4. Codex CLI Pitfalls Observed

Patterns worth watching more closely when Codex builds the Auth layer:

1. **Config/default drift between files.** The very first bug found was `config.py`'s default `DATABASE_URL` silently not matching `.env.example`. Watch for any new settings (JWT secret, token expiry, OAuth client IDs) having multiple sources of truth — always ask Codex to confirm a single settings-class origin, no hardcoded fallbacks duplicated elsewhere.
2. **Path/working-directory assumptions.** Two separate bugs (`.env` loading, skill file loading) stemmed from code not being anchored to the repo root, only working "by luck" depending on where the process was launched from. If Auth involves reading key files (e.g. RSA keys for JWT signing), explicitly ask Codex to anchor paths the same way and add a cwd-independence test, don't assume it generalizes.
3. **"Concurrent" tests that are actually sequential.** Codex initially described a race-condition test as "concurrent" when clarification was needed to confirm it actually used overlapping `asyncio.create_task` + a held lock, not just two sequential awaits. If Auth needs concurrency-sensitive logic (e.g. token refresh, session invalidation), demand the same proof standard: a test that shows both operations are genuinely in-flight at once, not just back-to-back.
4. **Retry logic scope creep risk.** Codex got this right for the LLM client (distinguishing retryable vs. non-retryable errors), but it required an explicit prompt requirement — it wasn't volunteered by default. If Auth involves calling any external identity provider, explicitly require retry logic to distinguish transient failures from auth failures (never retry a bad-credentials error).
5. **Ordering guarantees need an explicit tie-breaker requirement.** `created_at`-only sorting for chat messages was a real bug that required a dedicated review pass to catch, plus a follow-up fix (identity column + migration). If Auth needs to order anything time-sensitive (e.g. audit log of login attempts, token issuance order), ask upfront whether the sort key is provably unique/monotonic — don't assume timestamp precision is enough.
6. **Good habit confirmed, worth continuing to demand:** Codex does write structured, recoverable errors (not raw exceptions) when explicitly asked, and does isolate SDK/library dependencies behind protocols when asked. Keep making these explicit requirements in the Auth spec rather than assuming they'll happen by default.
7. **Review process that worked well:** checkpoint-sized builds (not one giant Phase at once) + requiring Codex to share actual code (not just prose summaries) before approval caught every bug above. None of these would have been caught by trusting a "N tests passed" summary alone. Keep this discipline for Auth.

---

## 5. Touchpoints With the Auth Layer

**Current state to be aware of / replace:**

- **`user_id` is accepted directly** in `POST /startups` and `POST /startups/{id}/chat` request bodies — no verification that the caller is authenticated as that user. Auth layer needs to replace this with a real identity mechanism (e.g. JWT in `Authorization` header, decoded to get the true `user_id`), removing `user_id` from request bodies once auth exists.
- **`app/services/startup_service.py`** already validates `user_id` exists in the `users` table before creating a startup (`UserNotFoundError` → 404) — this check should remain, but the *source* of `user_id` needs to shift from "trusted client input" to "derived from a verified token."
- **No endpoint is currently protected.** All 7 REST routes (`POST /startups`, `GET /startups/{id}`, `POST /startups/{id}/chat`, `GET .../documents/{doc_type}`, `GET .../documents/{doc_type}/history`, `POST .../advance-stage`, `PATCH .../stage`) are open. Once Auth exists, all of them need an authorization check: does the authenticated user own this `startup_id` (via `startups.user_id`)? The `chat` route already does a manual `startup.user_id != request.user_id` check inline — this pattern should be generalized into a reusable dependency once real auth exists, rather than duplicated per-route.
- **`app/api/dependencies.py`** currently only has `get_chat_client()`. This is the natural place to add an auth dependency (e.g. `get_current_user()`) that other routes can depend on.
- **`users` table already exists** (`app/models/user.py`) with `name`/`email` — Auth layer needs to decide whether to extend this table (password hash, OAuth provider ID, etc.) or add a separate `auth_credentials`-style table referencing it.
- **Tests currently create users directly via SQLAlchemy** (`User(name=..., email=...)`) bypassing any auth flow — once real auth exists, decide whether tests should go through the real signup/login flow or keep using direct DB fixtures for speed (both are reasonable; document the choice).

---

## 6. Current Status

- **All 5 phases of `coaching-harness-spec-en.md` complete**, reviewed checkpoint-by-checkpoint, code read directly (not just test-count trust) at every stage.
- **82 tests passing**, including:
  - Zero-DB unit tests (tools, orchestrator, stage logic)
  - Real-Postgres integration tests via testcontainers (versioning, race conditions, chat ordering, aliasing)
  - A full REST-level end-to-end test: `idea → lean_canvas → bmc`, covering readiness-does-not-advance, version history correctness, and sequential `/advance-stage` calls
- **All 6 acceptance criteria from spec §9 verified** with direct evidence (API calls / DB assertions), not inferred.
- **Committed and pushed** to `origin/main` (commit `2565661`), working tree clean, no uncommitted changes.
- **`.env` confirmed never committed**; `.gitignore` covers `.env`, `.venv/`, caches, egg-info.
- **Nothing outstanding** on the backend itself before starting Auth — coaching-harness is considered done for its defined scope (spec §10 explicitly excludes auth, frontend, and AgentOps from this phase).
