# Research Agent — `hs:plan`

**Status:** Proposed implementation plan for review
**Date:** 2026-08-06
**Workflow boundary:** This document completes `hs:plan`. It contains no implementation code and does not authorize `hs:build` until approved.

## Overview

This plan implements the approved Research Agent decisions in
`docs/research-agent-brainstorm.md` and
`docs/adr/research-agent-data-source.md`. Tavily Search + Extract is the first
provider, but all application code depends on a provider-neutral protocol. The
feature provides stage-gated agent research and an authenticated founder
endpoint, deterministic evidence/citation/legal handling, per-startup caching,
quota reservations, and AgentOps cost records.

The plan deliberately leaves `app/services/orchestrator.py` untouched. The
existing route-level AgentOps composition remains the integration seam.

## Two decisions resolved before the implementation sequence

### Per-turn research/document sequencing

A single `handle_turn()` call may technically receive multiple tool calls and
the existing orchestrator executes them in list order. However, the assistant
chooses all tool arguments in its first response; a later `generate_*` call in
that same batch cannot see the result of an earlier `research_web` call. It
would therefore be incorrect to claim that a same-turn Lean Canvas was
informed by same-turn research.

**Decision:** a research-dependent document generation is a two-turn flow.
The research turn calls `research_web` and returns grounded evidence; a later
turn calls `generate_lean_canvas`, `generate_bmc`, or another document tool
using the founder-visible evidence/context. The research prompt policy tells
the model not to co-emit a dependent `research_web` + `generate_*` batch. If a
model nevertheless emits both, the dispatcher may execute them in the existing
order, but the result is not labeled research-informed and the eval suite
asserts the supported two-turn behavior.

This costs one additional user/LLM turn and one provider call versus an
independent same-turn batch, increasing latency and potentially LLM spend. It
preserves correct grounding without changing the forbidden orchestrator file.
AgentOps must measure the research turn and generation turn separately; the
research provider latency is recorded inside `research_calls` and is included
in the enclosing `agent_turns.latency_ms`.

### Research provenance on document versions

**Decision:** no linkage from document rows/versions to `research_calls` in v1.
Research remains chat-scoped and is represented in the chat response, assistant
content, and AgentOps records. Existing document tables retain their exact
`version`/`is_current` write pattern and receive no nullable array or foreign
key. A later provenance feature can add a separate relation without changing
document version semantics or blocking a document write.

## Settled constraints carried into every checkpoint

- All new settings are `Settings` fields with aliases mirrored in `.env.example`.
- Provider SDK/HTTP details stay behind `ResearchProvider`.
- Errors cross service boundaries only as `{field, code, message}` or
  `{"ok": bool, "error": {...}}` structures.
- Research and cache access are startup-owner scoped; cache keys never permit
  cross-startup reuse.
- Every new append-only or ordering-sensitive table has a `sequence` identity
  column; joins to an agent turn use `turn_id` rather than timestamp inference.
- Quota reservation races use genuinely overlapping async tasks and database
  locking, not sequential awaits.
- The provider terms/DPA confirmation remains a production launch gate, not a
  reason to substitute a provider during this build.

## Checkpoint 0 — Schema, model registry, and configuration foundation

### Files to add or change

- `app/models/research.py` — add ORM models for:
  - `ResearchCall`: `id`, `sequence`, nullable `turn_id` FK to `agent_turns`,
    `startup_id`, `user_id`, nullable `session_id`, provider/operation/category,
    non-reversible `query_fingerprint`, provider request ID, provider/cache
    flags, credits reserved/charged, `cost_usd`, `pricing_unknown`, latency,
    status/error code, and `created_at`. Add indexes for startup/user/session,
    stage/category, and created-at error windows.
  - `ResearchCacheEntry`: `id`, `sequence`, `startup_id`, scoped `cache_key`,
    operation/category, normalized evidence payload JSONB, original
    `retrieved_at`, `expires_at`, and created/updated timestamps. Enforce a
    unique `(startup_id, cache_key)` constraint and index expiry.
  - `ResearchQuotaReservation`: `id`, `sequence`, user/session scope IDs,
    reserved call/credit units, charged/released units, reservation status,
    and timestamps. This is the auditable reservation ledger used to make
    rolling limits atomic.
- `app/db/base.py` — register all three models as the single Alembic model
  registry; do not create a second registry.
- `app/db/migrations/versions/20260806_0005_research_agent.py` — create the
  three tables, foreign keys, indexes, and constraints. The exact chain is:
  `revision = "20260806_0005"`, `down_revision = "20260801_0004"`; downgrade
  drops quota reservations, cache entries, then research calls and indexes.
- `tests/db/test_migrations.py` — extend the real Testcontainers/Postgres
  Alembic `upgrade(head)` inspection to assert all new tables, columns,
  nullability, identity sequences, FKs, indexes, and the scoped cache
  uniqueness constraint.
- `app/core/config.py` — add these exact fields and aliases/defaults:

  | Settings field | Alias | Default |
  |---|---|---:|
  | `research_enabled` | `RESEARCH_ENABLED` | `true` |
  | `research_provider` | `RESEARCH_PROVIDER` | `"tavily"` |
  | `tavily_api_key` | `TAVILY_API_KEY` | `""` |
  | `tavily_base_url` | `TAVILY_BASE_URL` | `"https://api.tavily.com"` |
  | `research_provider_timeout_seconds` | `RESEARCH_PROVIDER_TIMEOUT_SECONDS` | `15.0` |
  | `research_provider_max_retries` | `RESEARCH_PROVIDER_MAX_RETRIES` | `1` |
  | `research_session_hourly_call_limit` | `RESEARCH_SESSION_HOURLY_CALL_LIMIT` | `8` |
  | `research_session_daily_credit_limit` | `RESEARCH_SESSION_DAILY_CREDIT_LIMIT` | `20` |
  | `research_user_hourly_call_limit` | `RESEARCH_USER_HOURLY_CALL_LIMIT` | `20` |
  | `research_user_daily_credit_limit` | `RESEARCH_USER_DAILY_CREDIT_LIMIT` | `60` |
  | `research_cache_ttl_general_seconds` | `RESEARCH_CACHE_TTL_GENERAL_SECONDS` | `21600` |
  | `research_cache_ttl_news_seconds` | `RESEARCH_CACHE_TTL_NEWS_SECONDS` | `3600` |
  | `research_cache_ttl_pricing_seconds` | `RESEARCH_CACHE_TTL_PRICING_SECONDS` | `3600` |
  | `research_cache_ttl_legal_seconds` | `RESEARCH_CACHE_TTL_LEGAL_SECONDS` | `3600` |
  | `research_default_search_depth` | `RESEARCH_DEFAULT_SEARCH_DEPTH` | `"basic"` |
  | `research_max_results` | `RESEARCH_MAX_RESULTS` | `5` |
  | `research_pricing_enabled` | `RESEARCH_PRICING_ENABLED` | `true` |
  | `tavily_basic_search_credits` | `TAVILY_BASIC_SEARCH_CREDITS` | `1` |
  | `tavily_advanced_search_credits` | `TAVILY_ADVANCED_SEARCH_CREDITS` | `2` |
  | `tavily_extract_credits_per_five_urls` | `TAVILY_EXTRACT_CREDITS_PER_FIVE_URLS` | `1` |
  | `research_error_alert_threshold` | `RESEARCH_ERROR_ALERT_THRESHOLD` | `0.5` |
  | `research_error_alert_window_seconds` | `RESEARCH_ERROR_ALERT_WINDOW_SECONDS` | `300` |

  Add validation for positive limits/TTLs, allowed provider/depth values, and
  non-negative credit rates. Do not add any of these defaults to services.
- `.env.example` — mirror every alias above with the exact default and a short
  comment that `TAVILY_API_KEY` is required for live research while fixture
  tests inject a fake provider.
- `tests/core/test_research_config.py` — assert aliases, defaults, validation,
  and source inspection that rejects duplicate settings fallback literals.

### Checkpoint exit

The migration upgrades from `20260801_0004` to head on real Postgres, models are
registered once, and settings can be constructed in local/eval configurations
without importing a provider SDK.

## Checkpoint 1 — Provider protocol and normalized evidence

### Files to add or change

- `app/research/__init__.py` — package boundary; export only stable interfaces.
- `app/research/schemas.py` — typed public/internal models:
  `ResearchCategory`, `SearchDepth`, `EvidenceAuthority`, `EvidenceRecord`,
  `ResearchRequest`, `ResearchResult`, and structured legal notice. Each
  `EvidenceRecord` requires `source_id`, validated `http/https` URL, title,
  bounded excerpt, UTC `retrieved_at`, optional `published_at`, authority
  classification, and legal flag. A result includes call IDs, cache metadata,
  and `served_at` separately from original retrieval time.
- `app/research/protocol.py` — define `ResearchProvider` with:
  `async search(*, query: str, topic: str, search_depth: str, max_results: int,
  include_domains: list[str], start_date: date | None, end_date: date | None)
  -> ProviderSearchResponse` and
  `async extract(*, urls: list[str], query: str | None, extract_depth: str)
  -> ProviderExtractResponse`. Provider responses remain internal normalized
  records and never leak raw SDK/HTTP objects.
- `app/research/errors.py` — map timeout, rate-limit, unavailable, malformed
  response, and missing-key conditions to sanitized provider error codes.
- `app/research/tavily.py` — implement Tavily over the existing async HTTP
  stack (or isolate the Tavily SDK here if a dependency is deliberately added).
  Normalize Search `results[].url/title/content`, news publication metadata,
  request ID, and credit usage; normalize Extract URLs/content; stamp
  server-side UTC `retrieved_at`; validate URLs; bound excerpts; and classify
  authority/legal status without treating Tavily ranking or generated answers
  as proof. Set `include_answer=false` on search requests.
- `app/api/dependencies.py` — add `get_research_provider(settings)` that
  returns the configured Tavily adapter or a structured disabled/misconfigured
  error. It must not import Tavily outside `app/research/tavily.py`.
- `tests/research/test_tavily_adapter.py` — fake HTTP responses for search,
  news dates, extraction, malformed URLs, provider timeout/rate limit, and
  absent API key; assert normalized evidence and sanitized errors.

### Checkpoint exit

The adapter can be replaced by a fake implementing the same protocol, and no
service or route imports Tavily-specific response objects.

## Checkpoint 2 — Shared research service, quota reservations, and cache

### Files to add or change

- `app/services/research_quota_service.py` — implement the approved limits:
  session: 8 uncached calls/hour and 20 credits/24h; user: 20 uncached
  calls/hour and 60 credits/24h. Acquire transaction-scoped Postgres advisory
  locks for user and session in deterministic order, sum active reservation
  rows in the exact rolling windows, reject with structured
  `research_rate_limited` details (`scope`, `limit`, `retry_at`), then insert a
  reservation. Reconcile provider-reported credits and release unbilled
  failures; cache hits do not reserve.
- `app/services/research_cache_service.py` — build the exact versioned key from
  `startup_id`, provider, operation, normalized query/canonical URL, locale,
  topic, date range, domains, result limit, depth, authority/legal mode, and
  normalizer schema version. Enforce startup partition before lookup. Apply
  general 6-hour TTL, news/pricing/legal 1-hour TTL. On hit, return original
  `retrieved_at`, new `served_at`, and `cache_hit=true`; never call retrieval
  time “now.” Use atomic insert/update behavior for concurrent misses.
- `app/services/research_service.py` — shared use case for both entry points:
  validate request/category/jurisdiction, check cache, reserve quota, call the
  protocol, normalize/classify evidence, reconcile quota directly from the
  immediate provider outcome, write cache payload, and return `ResearchResult`
  plus the sanitized accounting outcome needed by its wrapper. It never imports
  `agentops_session()` or writes `research_calls`, and it must never mutate
  stage/document tables. Quota reconciliation is correctness-critical and does
  not depend on a best-effort telemetry row being written. Store query
  fingerprints rather than raw sensitive query text in AgentOps; raw cache
  payload is startup-scoped and bounded.
- `app/services/research_errors.py` — define recoverable structured errors for
  validation, rate limit, provider failure, cache conflict, and missing owner
  context. No raw provider exception crosses this boundary.
- `tests/services/test_research_quota_service.py` — real Postgres concurrency
  test with two overlapping `asyncio.create_task` calls and a synchronization
  barrier; assert only one reservation can consume the final unit. Cover both
  user and session limits, reconciliation, retry time, and cache-hit bypass.
- `tests/services/test_research_cache_service.py` — assert exact key
  sensitivity, per-startup isolation, TTL categories, expired-entry refresh,
  concurrent miss behavior, and preservation of `retrieved_at`/`served_at`.
- `tests/services/test_research_service.py` — fake provider tests for search,
  URL extraction, legal classification, structured errors, provider usage,
  cache hits, force refresh, and no document/stage mutation.

### Checkpoint exit

One shared service produces the same normalized result and quota/cache behavior
for a tool call and a standalone call, including under concurrent requests.

## Checkpoint 3 — Tool schema, stage gating, and same-turn safety

### Files to add or change

- `app/tools/schemas.py` — add `ResearchWebArgs`: non-empty query or bounded
  founder URLs, category, optional domain/date filters, optional jurisdiction
  required for legal category, `force_refresh`, and bounded `max_results`.
  Provider credentials, cache keys, and credit values are never model inputs.
- `app/tools/definitions.py` — register `research_web` and describe that it
  returns evidence records with URLs/retrieval dates and that legal results
  carry a mandatory disclaimer.
- `app/tools/validation.py` — reuse existing structured validation; add any
  cross-field error details for missing legal jurisdiction/query-vs-URL.
- `app/services/stage_tools.py` — add `research_web` to `idea`, `lean_canvas`,
  `bmc`, `swot`, `product_plan`, `marketing`, and `funding`; keep
  `completed` empty. Update exact-tuple stage tests.
- `app/services/tool_dispatcher.py` — accept injected research service and a
  route-created research execution context containing startup/user/session/
  turn/stage IDs. Dispatch `research_web` through the shared service and return
  `{"ok": true, "research": ...}` or the established structured error. Keep
  document persistence behavior unchanged.
- `app/services/research_prompt.py` — implement a `SkillLoader` composition
  decorator that appends the hard citation, uncertainty, legal disclaimer, and
  two-turn sequencing rules to stage skill content. This is passed into the
  existing orchestrator constructor at the route; `orchestrator.py` is not
  edited.
- `app/api/routes.py` — construct the research execution context alongside the
  existing `turn_id`, session, startup, and settings before composing the
  instrumented dispatcher. Construct `InstrumentedResearchService` around the
  real `ResearchService` at this route-level seam, using the same composition
  pattern as the existing AgentOps wrappers.
- `app/services/agentops/instrumented_research_service.py` — add
  `InstrumentedResearchService`, a composition wrapper around the real
  `ResearchService`. For every invocation (including cache hits and structured
  failures), it records exactly one `research_calls` row best-effort through
  `record_research_call()` after the wrapped service has returned its sanitized
  result/accounting outcome. It never changes the wrapped service's result or
  lets telemetry failure turn a founder response into a 500.
- `app/services/agentops/research_metrics_service.py` — add
  `record_research_call()`, the isolated `agentops_session()` writer used by
  `InstrumentedResearchService`. It persists turn/startup/user/session context,
  provider request ID, query fingerprint, credits, cost, latency, cache status,
  and sanitized error code. It is telemetry-only; quota reconciliation has
  already completed in `ResearchService` from the provider outcome.
- `tests/tools/test_research_tool.py`, `tests/services/test_stage_tools.py`,
  `tests/services/test_tool_dispatcher.py`, and
  `tests/services/test_research_prompt.py` — schema errors, exact stage access,
  ownership context, legal result shape, and prompt policy. Add a regression
  test proving a same-turn batch cannot be described as research-informed
  document generation. Add `tests/services/test_research_metrics.py` for the
  new wrapper's isolated commit, cache-hit row, exact `turn_id`, sequence, and
  best-effort metrics-failure behavior.

### Checkpoint exit

The real dispatcher can execute a validated research tool call at every
coaching stage except `completed`, and existing document tools/readiness tests
remain unchanged. Research-dependent generation is explicitly tested as a
subsequent turn.

## Checkpoint 4 — Founder endpoint and deterministic response policy

### Files to add or change

- `app/api/schemas.py` — add typed `ResearchRequest`, `ResearchEvidenceResponse`,
  `ResearchResponse`; extend `ChatResponse` with an optional structured
  `research` field without changing existing fields or readiness semantics.
- `app/services/research_response_policy.py` — after the composed orchestrator
  returns, collect `research_web` evidence from tool data, validate citation
  markers/source IDs, and return a sanitized content plus structured evidence.
  If evidence-backed prose lacks valid citations, replace the unsupported
  synthesis with a safe uncertainty/source summary. If any legal result is
  present, inject the exact mandatory notice into both content and structured
  response. Preserve original retrieval dates. This policy is called by the
  route outside `AgentOrchestrator` and is not a second orchestration branch.
- `app/api/routes.py` — add
  `POST /startups/{startup_id}/research`, protected by
  `require_startup_owner()`. Resolve/create the requested chat session for
  quota/AgentOps correlation, construct `InstrumentedResearchService` around
  the real `ResearchService` using the same route-level composition pattern as
  the Checkpoint 3 chat route, and call the wrapped service. Its telemetry write
  receives `turn_id=None`, because this standalone request has no
  `handle_turn()` call. Return structured evidence. Do not save chat messages
  unless the endpoint contract explicitly requests it; do not call
  `StageService` or `DocumentService`, and do not mutate stage/document state.
  Map all service errors to structured HTTP details, including 429 for rate
  limits. Update the chat route to apply response policy before saving assistant
  content and to return `research` data.
- `tests/api/test_research_routes.py` — owner/non-owner 404 behavior, session
  association, direct URL/search request, legal notice, cache hit, structured
  429, provider failure, no stage/document mutation, and chat response
  compatibility. Assert that a standalone research request produces exactly one
  `research_calls` row with `turn_id IS NULL`, distinct from the chat-route
  research case whose row has its route-created `turn_id`.
- `frontend/src/api/chat.ts` — type structured research evidence and the
  optional `ChatResponse.research` field; preserve the existing typed client.
- `frontend/src/api/research.ts` — add typed founder endpoint request/response
  wrapper using `apiRequest`, never ad-hoc fetch.
- `frontend/src/features/research/ResearchEvidence.tsx` — render source title,
  direct URL, original retrieval date, optional publication date, bounded
  excerpt, uncertainty/authority label, and the mandatory legal notice.
- `frontend/src/features/research/ResearchPanel.tsx` — accessible founder
  query/URL/category/jurisdiction controls, loading/error/rate-limit states,
  and retry/refresh behavior. It uses the startup-scoped endpoint and does not
  put research state in Zustand.
- `frontend/src/features/chat/ChatPanel.tsx` and `MessageList.tsx` — show
  immediate structured research evidence and preserve citations in assistant
  Markdown/history. Completed-stage chat remains read-only, but the standalone
  research panel remains available as specified.
- Relevant frontend tests: `frontend/src/api/chat.test.ts`, new research API
  tests, `ResearchEvidence.test.tsx`, `ResearchPanel.test.tsx`, and updates to
  `ChatPanel.test.tsx`/`MessageList.test.tsx`.

### Checkpoint exit

A founder can trigger research against an owned startup, see every URL and
retrieval date, see the legal disclaimer when applicable, and receive
structured quota/provider errors. Existing chat response consumers still parse
session ID, message, and stage readiness.

## Checkpoint 5 — AgentOps research accounting and alerting

### Files to add or change

- `app/services/agentops/research_metrics_service.py` and
  `app/services/agentops/instrumented_research_service.py` — retain the
  Checkpoint 3 telemetry ownership: `InstrumentedResearchService` appends one
  `research_calls` row per invocation (including cache hits with
  `provider_call_made=false` and zero charged credits) through the metrics
  service's isolated `agentops_session()` write. This checkpoint extends that
  established path only as needed for pricing and alerting; it does not move
  the write into `ResearchService`. Metrics failures remain logged best-effort
  and never turn a successful founder response into a 500.
- `app/services/agentops/pricing.py` — extend the existing pricing module with
  Tavily operation credit rates from `Settings`; unknown/disabled pricing gives
  `cost_usd=None` and `pricing_unknown=true`, never zero. Keep the model pricing
  API backward compatible.
- `app/services/agentops/alerting_service.py` — extend the metric union with
  `research_error_rate`, count only provider infrastructure failures
  (`provider_error`, `timeout`, `rate_limited_provider`, and equivalent
  transport statuses), and exclude cache hits, validation, quota rejection,
  and malformed founder input. Reuse warning-only `alert_events` behavior and
  injected time. Threshold/window defaults come from the new Settings fields.
- `app/services/agentops/instrumented_tool_dispatcher.py` — retain one normal
  tool-call log for `research_web`; do not duplicate it as an AgentOps research
  row. `InstrumentedResearchService` owns the separate per-invocation research
  telemetry row; `ResearchService` owns only correctness-critical quota/cache
  state.
- `tests/services/test_research_metrics.py` — extend the Checkpoint 3 wrapper
  coverage for unknown pricing and provider-attempt accounting while retaining
  isolated commit, cache-hit row, exact `turn_id`, sequence, and best-effort
  failure behavior.
- Extend `tests/services/test_agentops_metrics_services.py` for
  `research_error_rate`, zero-volume windows, stage scope, and excluded
  non-infrastructure statuses.

### Checkpoint exit

Every research invocation has auditable cost/cache/latency data, every provider
attempt is joinable to its turn when one exists, and on-demand research error
alerts follow the existing warning-only AgentOps semantics.

## Checkpoint 6 — Deterministic evals, integration verification, and review gate

### Files to add or change

- `evals/fixtures/research_lean_canvas.json` — fixture conversation with a
  research-only Lean Canvas turn, grounded source IDs/citations, and a later
  document-generation turn; assert no stage auto-advance.
- `evals/run.py` — add a fixture-backed fake `ResearchProvider`/research service
  and research assertions while keeping the suite DB-free and live-key-free.
  The real tool schema, stage gate, response policy, and orchestrator loop are
  still exercised.
- `tests/evals/test_agentops_eval_runner.py` — assert the new fixture passes and
  fails when citations, source URLs/retrieval dates, or two-turn sequencing are
  broken.
- `tests/services/test_orchestrator.py` — run the existing suite unmodified as
  a guard that `app/services/orchestrator.py` remains untouched.
- `tests/api/test_routes.py` and focused frontend tests — regression coverage
  for existing chat/document/stage behavior and API response compatibility.

### Verification order

1. Focused schema/settings/provider tests.
2. Real migration upgrade test against Postgres.
3. Real concurrent quota/cache tests.
4. Research service/tool/API tests.
5. AgentOps metrics/alert tests.
6. `python -m evals.run` with the deterministic fixture suite.
7. Backend `python -m ruff check app tests evals` and `python -m pytest`.
8. Frontend `npm --prefix frontend run lint`, `typecheck`, `test`, and `build`.
9. Review the final diff for the invariant that `orchestrator.py` is unchanged,
   migration chain is linear, all settings are mirrored, and no generated
   files or unrelated worktree changes are staged.

## Completion criteria

- The migration upgrades cleanly from `20260801_0004` and downgrades cleanly.
- Research calls, cache entries, and quota reservations have ownership-safe
  foreign keys, sequence ordering, and no global cache path.
- Tavily is replaceable through `ResearchProvider`; no provider SDK leaks into
  services, routes, or orchestrator logic.
- Per-user/per-session reservations are atomic under real concurrent overlap;
  cache hits do not consume provider quota.
- Every surfaced evidence record includes a direct URL and original UTC
  retrieval timestamp; cache hits preserve that timestamp and expose
  `served_at`/`cache_hit`.
- Unsupported factual synthesis is not presented as settled fact, and every
  legal/regulatory result visibly carries the exact non-legal-advice notice.
- Research is available to all seven coaching stages and not `completed` agent
  tool access; standalone founder research remains owner-protected at any
  stage.
- Document versions have no research linkage in v1 and retain their existing
  atomic version/is_current semantics.
- `research_calls` records provider/cache/cost/latency outcomes with nullable
  `turn_id` only for standalone requests; unknown pricing is explicit.
- Existing AgentOps, orchestrator, auth/ownership, document, frontend, and eval
  regression suites pass.
- The final implementation leaves `app/services/orchestrator.py` unchanged.

## Remaining explicit ambiguity

No architecture choice remains open after the two resolutions above. The only
non-technical gate carried from the approved ADR is written Tavily
commercial-use/DPA confirmation before public production. It does not block
building against the adapter now and must not be silently treated as resolved
by code.
