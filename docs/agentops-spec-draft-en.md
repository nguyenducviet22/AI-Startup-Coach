# AgentOps Spec (Draft) — AI Startup Coach

**Version:** 0.1 (draft — for `hs:brainstorm`, not yet approved for `hs:plan`/`hs:build`)
**Purpose:** Technical spec to hand off to Codex (via the `hs:brainstorm → hs:plan → hs:build → hs:code-review → hs:ship` workflow) for building the AgentOps phase of AI Startup Coach — the 4th phase, after coaching-harness, Auth layer, and Frontend/UI.

This draft exists to seed `hs:brainstorm`. The initial tradeoffs have been resolved in §12 before moving to `hs:plan`.

---

## 1. Overview

`coaching-harness` was explicitly scoped to exclude AgentOps (spec §10: "detailed logging, cost tracking, eval sets — to be built once the core harness is stable"). The core harness, auth layer, and frontend are now done. This phase adds an observability + regression-safety layer around the existing `AgentOrchestrator` loop, **without changing its external behavior or the student-facing API contract.**

Scope for this phase:
1. Structured request/response logging for the orchestrator loop
2. LLM cost/token tracking, broken down per coaching stage
3. Tool-call latency instrumentation
4. Error-rate alerting
5. A baseline eval suite to catch regressions when skill content (`skills/*.md`) or prompts change

Explicitly not in scope (see §11).

---

## 2. Architecture

AgentOps should sit **alongside** the existing call graph as an instrumentation layer, not fork it:

```
API routes (app/api/routes.py)
  -> AgentOrchestrator.handle_turn()
      -> ChatCompletionClient.create_chat_completion()   <- instrument here (LLM calls)
      -> ToolDispatcher.execute()                         <- instrument here (tool calls)
```

Decision from `hs:brainstorm`: use wrapper-based instrumentation plus a thin turn-level recorder, all via composition. `orchestrator.py` itself is not modified.

- `InstrumentedChatClient` implements the existing `ChatCompletionClient` protocol and wraps `OpenRouterChatClient`.
- `InstrumentedToolDispatcher` wraps `ToolDispatcher` by composition, keying off the dispatcher's existing structured result shape.
- `InstrumentedAgentOrchestrator` wraps `AgentOrchestrator` by composition, holding a real `AgentOrchestrator` instance, calling `handle_turn()` on it, timing the call, and reading `startup_id`/`session_id`/`stage` from the same `StartupContext`/`OrchestratorResult` the route already has. It is explicitly **not** a subclass and does not thread new data through `AgentOrchestrator` internals.

Construction happens at the route-level call site, after the route knows the `turn_id`, `startup_id`, `session_id`, and `stage`. `get_chat_client()` in `app/api/dependencies.py` stays unchanged and returns the raw `OpenRouterChatClient`; `app/api/routes.py::chat()` wraps that client, constructs the instrumented tool dispatcher, and wraps `AgentOrchestrator` with `InstrumentedAgentOrchestrator` at the same call site where `ToolDispatcher(document_service=...)` and `AgentOrchestrator(...)` are currently built. This keeps observability alongside the loop without coupling it to the loop implementation.

---

## 3. Scope Breakdown

### 3.1 Orchestrator request/response logging
Every `handle_turn()` call should produce a durable, structured record of: which startup/session/stage it ran in, the outbound message count sent to the LLM, whether tool calls occurred, the final response length, and total turn latency. This is distinct from `chat_messages` (student-visible conversation) — it's an operational audit trail, closer in spirit to `chat_messages.tool_call_data` but capturing timing/status, not content-for-replay.

### 3.2 LLM cost/token tracking per stage
Every `create_chat_completion()` call should record `prompt_tokens`, `completion_tokens`, `total_tokens` (from the response's `usage` field — note `orchestrator.py`'s existing `_get()` helper already handles the dict-vs-object duality the OpenAI/OpenRouter SDK response can take; the instrumentation should reuse that same duality-safe access pattern rather than assuming one shape), model name, and a derived `cost_usd`.

`OPENROUTER_MODEL` is currently an unset placeholder (coaching-harness handoff, Known TODOs). Cost tracking cannot hardcode a per-model price implicitly. Use a small, explicit pricing table in `app/services/agentops/pricing.py`, controlled by `Settings`, keyed by model slug, with `cost_usd = null` + a `pricing_unknown` flag when the running model isn't in the table — never silently reported as `$0`.

### 3.3 Tool-call latency instrumentation
Every `ToolDispatcher.execute()` call should record latency, `tool_name`, `current_stage`, and outcome (`ok` / `tool_not_available_for_stage` / validation error / persistence error) — the existing structured `{"ok": bool, ...}` return shape already distinguishes these cleanly; instrumentation should key off `result["ok"]` and `result["error"]["type"]` rather than re-deriving status another way.

### 3.4 Error-rate alerting
Track error rate over a rolling window, per stage and/or globally, and raise an alert when a configurable threshold is crossed. LLM error rate counts any `llm_calls.status != 'success'`. Tool error rate counts only `tool_calls_log.status IN ('error', 'persistence_error')`; `validation_error` and `not_allowed` are intentionally excluded because they reflect model/tool-use quality, not infrastructure or dispatcher failure.

Decision from `hs:brainstorm`: write to an `alert_events` table only for this phase. No webhook/email delivery is built now; outbound notification is a later increment, consistent with the project's pattern of shipping the durable-record layer first and building UI/consumption on top (mirrors how `stage_readiness` was built as data first, then surfaced in the frontend).

### 3.5 Baseline eval suite
A suite of scripted conversations per stage (at minimum: `idea`, `lean_canvas`, `bmc`, per coaching-harness spec §9's existing acceptance-criteria precedent of an idea→lean_canvas→bmc E2E test) that assert: the right tool gets called, required fields are populated, `check_stage_readiness` returns sane structured output, and stage never auto-advances. Run against a **recorded/fixture** `ChatCompletionClient` implementation for deterministic CI runs, with an optional real-model mode for periodic drift checks.

Decision from `hs:brainstorm`: start with hand-authored deterministic JSON fixtures for the CI gate. Captured-then-frozen real-model runs are deferred to a later, separate "drift check" mode, not part of this phase's CI gate. The eval runner uses the real `AgentOrchestrator` plus `ToolDispatcher(document_service=None)`, so tool schema validation is real while the suite stays DB-free and live-API-free.

---

## 4. Database Schema (proposed)

Append-only tables — no `version`/`is_current` pattern here (that pattern exists for student-authored documents with edit history; these are immutable log rows). Each gets a `sequence` identity column following the `chat_sessions`/`chat_messages` precedent, since `created_at`-only ordering was a real bug caught in that phase (coaching-harness handoff, Pitfall 5) — don't repeat it.

```sql
CREATE TABLE agent_turns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sequence BIGINT GENERATED BY DEFAULT AS IDENTITY,
    startup_id UUID REFERENCES startups(id) NOT NULL,
    session_id UUID REFERENCES chat_sessions(id),
    stage VARCHAR(50) NOT NULL,
    tool_call_count INT NOT NULL,
    status VARCHAR(20) NOT NULL,       -- 'pending' | 'success' | 'error'
    latency_ms INT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE llm_calls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sequence BIGINT GENERATED BY DEFAULT AS IDENTITY,
    turn_id UUID REFERENCES agent_turns(id) NOT NULL,  -- joins calls to the exact handle_turn() record; avoids timestamp-based inference and avoids repeating the chat_messages ordering mistake.
    startup_id UUID REFERENCES startups(id) NOT NULL,
    session_id UUID REFERENCES chat_sessions(id),
    stage VARCHAR(50) NOT NULL,
    model VARCHAR(255) NOT NULL,
    prompt_tokens INT,
    completion_tokens INT,
    total_tokens INT,
    cost_usd NUMERIC(12,6),
    pricing_unknown BOOLEAN NOT NULL DEFAULT false,
    latency_ms INT NOT NULL,
    status VARCHAR(20) NOT NULL,       -- 'success' | 'timeout' | 'rate_limited' | 'error'
    error_code VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE tool_calls_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sequence BIGINT GENERATED BY DEFAULT AS IDENTITY,
    turn_id UUID REFERENCES agent_turns(id) NOT NULL,  -- joins calls to the exact handle_turn() record; avoids timestamp-based inference and avoids repeating the chat_messages ordering mistake.
    startup_id UUID REFERENCES startups(id) NOT NULL,
    tool_name VARCHAR(100) NOT NULL,
    stage VARCHAR(50) NOT NULL,
    latency_ms INT NOT NULL,
    status VARCHAR(20) NOT NULL,       -- 'ok' | 'validation_error' | 'not_allowed' | 'persistence_error'
    error_type VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE alert_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sequence BIGINT GENERATED BY DEFAULT AS IDENTITY,
    metric_name VARCHAR(100) NOT NULL,   -- e.g. 'llm_error_rate', 'tool_error_rate'
    scope VARCHAR(100),                  -- e.g. stage name, or NULL for global scope
    threshold NUMERIC NOT NULL,
    observed_value NUMERIC NOT NULL,
    window_seconds INT NOT NULL,
    severity VARCHAR(20) NOT NULL,       -- 'warning' only for this phase
    triggered_at TIMESTAMPTZ DEFAULT now(),
    resolved_at TIMESTAMPTZ
);
```

Although the DB keeps `DEFAULT gen_random_uuid()` for consistency with the existing schema, `agent_turns.id` is generated client-side with `uuid.uuid4()` before the pre-insert so child `llm_calls` and `tool_calls_log` rows can carry the exact `turn_id` during the same `handle_turn()` call.

`turn_id` exists on `llm_calls` and `tool_calls_log` so every LLM call and tool call can be joined back to the exact turn that produced it. Without this, reconstructing "which LLM/tool calls belong to this turn" would require timestamp-based inference, which is the same class of bug the `chat_messages.sequence` fix already corrected once; don't reintroduce it here.

Indexes:

- `ix_llm_calls_created_at` on `llm_calls(created_at)`
- `ix_llm_calls_stage_created_at` on `llm_calls(stage, created_at)`
- `ix_tool_calls_log_created_at` on `tool_calls_log(created_at)`
- `ix_tool_calls_log_stage_created_at` on `tool_calls_log(stage, created_at)`

These exist because `alerting_service.evaluate_error_rate(...)` filters by `created_at` windows globally and by `(stage, created_at)` for stage-scoped alerts.

Alert severity is warning-only for this phase. A second threshold/tier such as `critical` is deferred until there is a real ops dashboard or notification workflow that needs it.

Decision from `hs:brainstorm`: `eval_runs`/`eval_cases` stay out of the main Postgres database for this phase. Eval execution is DB-free, and eval results are CI artifacts (JSON primary, JUnit-style deferred until needed), not app tables, until there is a real ops dashboard or longitudinal reporting need.

---

## 5. Service Layer (proposed)

Following the approved `app/services/agentops/` organization:

- `app/services/agentops/llm_metrics_service.py` — `record_llm_call(...)`, used by the instrumented chat client wrapper.
- `app/services/agentops/tool_metrics_service.py` — `record_tool_call(...)`, used by the instrumented tool dispatcher wrapper.
- `app/services/agentops/turn_metrics_service.py` — `start_turn(...)` and `finish_turn(...)`, used by the instrumented orchestrator wrapper.
- `app/services/agentops/session.py` — `agentops_session()`, the isolated AsyncSession helper used by every AgentOps metrics write.
- `app/services/agentops/alerting_service.py` — `evaluate_error_rate(metric_name, scope, window_seconds, threshold) -> ErrorRateEvaluation`, callable on demand. The returned dataclass includes `total_count`, `error_count`, `observed_value`, `alert_inserted`, `severity`, and `reason` (including `not_enough_data` for zero-volume windows).
- `app/services/agentops/instrumented_chat_client.py`, `instrumented_tool_dispatcher.py`, and `instrumented_orchestrator.py` — instrumented wrappers live together here. `InstrumentedAgentOrchestrator` wraps the real orchestrator by composition and is not placed inside `app/services/orchestrator.py`.
- `app/services/agentops/pricing.py` — explicit in-code model→price table, controlled by `Settings`.
- `evals/` at repo root (sibling to `app/`, `frontend/`) — eval suite runner + fixtures, mirroring how `skills/` sits outside `app/` as content, not code.

All new settings (alert thresholds, window sizes, pricing table path) go through `app/core/config.py::Settings` — **single source of truth, no hidden fallback defaults duplicated elsewhere.** This was the very first bug found in the original coaching-harness build (config/default drift) and should not recur.

All new service errors should follow the project's established recoverable-structured-error convention (`{field, code, message}` per `auth_service.py`, or the tool dispatcher's `{"ok": bool, "error": {"type", "message", "details"}}` shape) rather than raising raw exceptions across service boundaries.

---

## 6. Instrumentation Points in Existing Code

| File | Change |
|---|---|
| `app/api/dependencies.py` | No changes — `get_chat_client()` keeps returning the raw `OpenRouterChatClient`. |
| `app/api/routes.py` (`chat()`) | Once `turn_id`/`startup_id`/`session_id`/`stage` are known, the raw chat client is wrapped, `ToolDispatcher(document_service=document_service)` construction is wrapped with an instrumented variant, and `AgentOrchestrator(...)` construction is wrapped by `InstrumentedAgentOrchestrator` at the route level. |
| `app/services/orchestrator.py` | **No changes** — wrapped via composition at the route level. |
| `app/llm/openrouter.py` | No changes to retry/backoff logic itself — only wrapped, not modified. Preserve the existing transient-vs-non-transient distinction (`APITimeoutError`/`APIConnectionError`/`RateLimitError`/transient `APIStatusError` retried; 401/400 not retried) untouched. |

---

## 7. API Endpoints (Deferred — not built this phase)

Decision from `hs:brainstorm`: `/agentops/*` endpoints are deferred entirely for this phase. These endpoints expose cross-startup operational data and need a separate ops-role authorization model, which is not being introduced now. Keep the proposed shape here for a later scoped ops-auth/API phase.

| Method | Path | Description |
|---|---|---|
| GET | `/agentops/llm-calls` | Paginated LLM call log, filterable by startup/stage/status |
| GET | `/agentops/tool-calls` | Paginated tool call log, filterable by startup/stage/status |
| GET | `/agentops/cost-summary` | Aggregated token/cost totals, groupable by stage/day |
| GET | `/agentops/alerts` | Active/recent alert events |
| POST | `/agentops/evals/run` | Trigger an eval suite run (dev/CI use, not student-facing) |
| GET | `/agentops/evals/{run_id}` | Eval run result detail |

---

## 8. Acceptance Criteria (for review once Codex finishes building)

- [ ] Every `create_chat_completion()` call made through the chat route produces exactly one `llm_calls` row, with token counts populated when the provider returns `usage`, and `pricing_unknown=true` (never a silently-wrong `$0`) when the model isn't in the pricing table.
- [ ] Every `ToolDispatcher.execute()` call made through the chat route produces exactly one `tool_calls_log` row, with `status` matching the dispatcher's own `ok`/error-type result.
- [ ] Every `InstrumentedAgentOrchestrator.handle_turn()` call made through the chat route produces exactly one `agent_turns` row, and related `llm_calls`/`tool_calls_log` rows carry that `turn_id`.
- [ ] `orchestrator.py`'s existing test suite passes unmodified; `orchestrator.py` itself remains untouched.
- [ ] Alert evaluation is provably deterministic and testable without a real clock/scheduler dependency (inject a time source, same spirit as testing refresh-token expiry logic in the auth layer).
- [ ] The eval suite runs against a fixture-backed `ChatCompletionClient` in CI (no live API key required) and fails the build on a broken tool-call/readiness assertion.
- [ ] No new endpoint or logging path can leak one startup's data to another — cross-startup aggregate views are explicitly ops-only, not exposed to `require_startup_owner`-protected student routes.
- [ ] All new settings live in `Settings` with no hardcoded fallback duplicated elsewhere.

---

## 9. Known Constraints Carried Over From Prior Phases

(From the coaching-harness, auth-layer, and frontend-ui handoff notes' "Pitfalls" sections — apply the same discipline here.)

- Any file/path access must be anchored to `ROOT_DIR`, not cwd (`.env` and skill-loading bugs both came from this).
- Any "concurrent" test claim must show real overlapping `asyncio.create_task` + a held lock, not sequential awaits dressed up as concurrent.
- Retry logic must explicitly distinguish transient vs. non-transient failures — this was not volunteered by default in the original build and had to be explicitly required.
- New ordering-sensitive data needs a provably-unique tie-breaker, not `created_at` alone (hence `sequence` columns above).
- Config drift between `Settings` and `.env.example` was the first bug found in the original build — don't reintroduce it for new AgentOps settings.
- Checkpoint-sized builds with actual code shown for review (not prose "N tests passed" summaries) is the review discipline that caught every prior bug — continue it here.

Resolved `hs:brainstorm` decisions are listed in §12 and remain binding for this phase.

---

## 10. Touchpoints With Frontend (for a later phase, not this one)

Per the frontend-ui handoff's "Touchpoints With AgentOps" section, the frontend has already enumerated the events it expects to eventually instrument (auth bootstrap, chat send latency, stage transitions, document generation visibility, etc.). This backend phase should produce data shapes compatible with that list, but **wiring the frontend itself is out of scope for this phase** — see §11.

---

## 11. Out of Scope for This Phase

- Any frontend/UI changes (dashboards, charts) — backend/data layer only.
- Outbound alert delivery (email/webhook/Slack) beyond a durable `alert_events` table.
- An ops-role/admin-auth system and all `/agentops/*` endpoints.
- DB-backed eval history (`eval_runs`/`eval_cases`) until there is a real ops dashboard or longitudinal reporting need.
- Real-time/streaming metrics (this stays request/response-cycle instrumentation, matching the existing non-streaming chat design).
- Automated model-pricing sync from OpenRouter's live pricing API — the pricing table starts as a manually maintained config.

---

## 12. Resolved Questions From `hs:brainstorm`

1. Wrapper/composition over inline instrumentation.
2. Alerts: durable `alert_events` table only for this phase, no webhook/email.
3. Eval fixtures: start hand-authored/deterministic; captured-then-frozen real-model runs are a later, separate "drift check" mode, not part of this phase's CI gate.
4. `eval_runs`/`eval_cases` stay out of the main Postgres DB for now — CI artifacts (JSON/JUnit-style), not app tables.
5. `/agentops/*` endpoints are deferred entirely for this phase — no ops-role auth model is being introduced now.
