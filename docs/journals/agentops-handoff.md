# AgentOps Handoff Note

**Status:** AgentOps phase complete, reviewed, committed, and pushed to `main`.
**Commit:** `327df8e` — "Add AgentOps instrumentation and evals"
**Repo:** https://github.com/nguyenducviet22/AI-Startup-Coach
**Base context:** Coaching harness, auth layer, and frontend/UI are already complete on `main`.
**Full spec:** `docs/agentops-spec-draft-en.md`

---

## 1. Architecture Overview

```
app/api/routes.py::chat()
  -> raw ChatCompletionClient from get_chat_client()
      -> InstrumentedChatClient
  -> ToolDispatcher(document_service=document_service)
      -> InstrumentedToolDispatcher
  -> AgentOrchestrator(...)
      -> InstrumentedAgentOrchestrator
          -> AgentOrchestrator.handle_turn()
```

AgentOps was implemented as a composition-wrapper layer around the existing
orchestrator loop. `app/services/orchestrator.py` itself was deliberately not
modified, so the student-facing `AgentOrchestrator.handle_turn()` contract and
the `/chat` route response shape stay unchanged.

**Key modules:**
- `app/services/agentops/instrumented_chat_client.py` wraps the configured raw
  `ChatCompletionClient`, measures LLM latency, extracts usage tokens/model, and
  records `llm_calls` rows best-effort.
- `app/services/agentops/instrumented_tool_dispatcher.py` wraps
  `ToolDispatcher.execute()`, measures tool latency, maps structured dispatcher
  outcomes to AgentOps statuses, and records `tool_calls_log` rows best-effort.
- `app/services/agentops/instrumented_orchestrator.py` wraps the real
  `AgentOrchestrator` by composition, creates/finalizes one `agent_turns` row per
  route-level `handle_turn()` call, and treats `agent_turns.status` as a thin
  crash signal.
- `app/services/agentops/session.py` provides `agentops_session()`, a fresh
  AsyncSession helper for telemetry writes that is separate from the request's
  student-facing session/transaction.
- `app/services/agentops/turn_metrics_service.py`,
  `llm_metrics_service.py`, and `tool_metrics_service.py` perform one immediate
  DB write per call, each through an isolated AgentOps session.
- `app/services/agentops/pricing.py` contains a small explicit in-code pricing
  dictionary controlled by `Settings.agentops_pricing_enabled`.
- `app/services/agentops/alerting_service.py` provides deterministic,
  on-demand error-rate evaluation and durable `alert_events` inserts.
- `evals/run.py` and `evals/fixtures/*.json` provide a deterministic, DB-free,
  fixture-backed baseline eval suite.

**Schema:**
- `agent_turns` is the parent turn record, with a monotonic `sequence` identity
  column and a client-generated `id` used as `turn_id` by child calls.
- `llm_calls` records model, token counts, cost/pricing status, latency, status,
  and error code for every wrapped LLM call.
- `tool_calls_log` records tool name, stage, latency, mapped status, and error
  type for every wrapped tool dispatch.
- `alert_events` stores durable warning-only alert events for error-rate
  threshold crossings.

---

## 2. Key Design Decisions

| Decision | Why |
|---|---|
| **Composition wrappers, not inline orchestrator edits** | Keeps `AgentOrchestrator.handle_turn()` behavior stable and leaves the core loop free of telemetry concerns. The chat route is the one place that knows `turn_id`, `startup_id`, `session_id`, and `stage`, so it wires the wrappers there. |
| **`get_chat_client()` stays raw** | `turn_id` and session context are only known inside `app/api/routes.py::chat()`. Instrumenting at the dependency would either miss required context or require threading telemetry state through unrelated layers. |
| **Two-phase `agent_turns` write** | `start_turn()` pre-inserts `status='pending'` before the real turn runs; `finish_turn()` updates exactly that row to `success` or `error`. This records escaped crashes while preserving one row per route-level turn. |
| **Client-side `turn_id` generation** | The route creates `uuid.uuid4()` before `start_turn()` so `llm_calls` and `tool_calls_log` can reference the exact parent turn as they occur. The DB still keeps `DEFAULT gen_random_uuid()` for schema consistency, but the runtime parent ID is generated before the pre-insert. |
| **Separate AgentOps DB session per metrics write** | Telemetry writes must survive rollback or exceptions in the student-facing request transaction. Each metrics service opens its own AsyncSession, writes, commits immediately, and closes. |
| **Best-effort metrics writes** | Instrumentation must never turn a successful student chat turn into a 500. The wrappers catch/log metrics-recording failures and continue, without catching or hiding failures from the underlying LLM/tool/orchestrator call itself. |
| **Latency timer stops before telemetry write** | Separate AgentOps sessions add connection/commit overhead. LLM and tool `latency_ms` measure only the wrapped LLM/tool call, then telemetry is written afterward so AgentOps overhead does not pollute the metric it exists to measure. |
| **`agent_turns.status` is a thin crash signal** | `agent_turns.status='error'` only means `AgentOrchestrator.handle_turn()` let an exception escape. Recoverable LLM provider failures can still produce a successful student response, so real error-rate truth lives in `llm_calls.status` and `tool_calls_log.status`. |
| **Error-rate definitions are metric-specific** | `llm_error_rate` counts any `llm_calls.status != 'success'`. `tool_error_rate` counts only `tool_calls_log.status IN ('error', 'persistence_error')`; `validation_error` and `not_allowed` are excluded because they reflect model/tool-use quality, not infrastructure failure. |
| **Zero-volume alert windows return `not_enough_data`** | A window with no rows should not divide by zero or spuriously report 0%/100%. The service returns an `ErrorRateEvaluation` with `observed_value=None` and inserts no alert. |
| **Warning-only, no dedup, no scheduler** | Alerting is durable data only in this phase. Threshold crossings insert warning rows; no webhook/email, critical tier, deduplication, or background scheduler exists yet. |
| **Eval suite is DB-free and deterministic** | Evals run the real `AgentOrchestrator` with `ToolDispatcher(document_service=None)` and a scripted fake chat client. Tool schema validation is real, but CI does not need Postgres, a live model, or an API key. |
| **Eval results are JSON artifacts, not app tables** | `eval_runs`/`eval_cases` stay out of Postgres until there is an ops dashboard or longitudinal reporting need. |

---

## 3. Known Technical Debt / TODOs

- **No `/agentops/*` API endpoints.** The proposed ops endpoints are deferred
  entirely. They need an ops-role authorization model before exposing
  cross-startup operational data.
- **No ops-role/admin auth.** Student-facing ownership auth exists, but no
  privileged operational access model has been designed or implemented.
- **No outbound alert delivery.** Alerting writes only to `alert_events`; email,
  webhook, Slack, or dashboard delivery is a later phase.
- **Warning-only alert severity.** There is no `critical` threshold/tier yet.
  Add it only when there is a concrete notification/dashboard workflow that
  needs escalation semantics.
- **No alert deduplication/resolution workflow.** Repeated calls to
  `evaluate_error_rate()` can insert repeated alert rows for the same ongoing
  condition. `resolved_at` is schema space for a future lifecycle, not used now.
- **No scheduler/cron.** Alert evaluation is callable on demand only. A future
  job runner can call `evaluate_error_rate()` with explicit metric/scope/window
  settings.
- **Eval fixtures are hand-authored only.** Captured-then-frozen real-model runs
  are intentionally deferred to a separate drift-check mode.
- **No DB-backed eval history.** Eval artifacts are JSON files; `eval_runs` and
  `eval_cases` remain deferred until longitudinal reporting is useful.
- **No index on child `turn_id` yet.** `llm_calls.turn_id` and
  `tool_calls_log.turn_id` have FK constraints, but there is no explicit index
  on those columns. This is not a known performance problem yet; add indexes if
  future dashboards frequently join from turns to child calls at scale.
- **Pricing table is intentionally small and manual.** Unknown models return
  `cost_usd=None` and `pricing_unknown=True`, never a silent zero. Automated
  OpenRouter pricing sync is deferred.
- **Eval runner is source-tree tooling.** Run it from a checkout with
  `python -m evals.run`; it is intentionally not included in the installed app
  wheel.

---

## 4. Pitfalls Observed This Phase

Patterns worth watching more closely when Codex builds the next phase:

1. **Paste actual code/diffs, not summaries or commands-to-run.** The most useful
   review feedback came from seeing the real files and real diffs. A prose
   "N tests passed" summary is not enough for this project.
2. **Verify real DB-backed behavior, not just syntax.** `compileall` only proved
   parsing. The migration needed a real Alembic upgrade against Postgres, and
   metrics services needed real DB assertions to prove constraints, commits, and
   rollback isolation.
3. **Watch for spec/code drift after decisions change.** The design moved from
   dependency-level LLM instrumentation to route-level composition, then from
   broad tool error counting to infrastructure-only tool error counting. The
   spec had to be re-read and corrected after each decision.
4. **Do not create duplicate registries.** Adding AgentOps models initially
   risked making `app/models/__init__.py` a second model registry. The project
   convention is that `app/db/base.py` is the single Alembic model-registration
   point.
5. **Separate telemetry transactions create new measurement traps.** Once every
   metrics write commits independently, timing blocks must stop before the
   telemetry write starts. Otherwise AgentOps overhead contaminates LLM/tool
   latency numbers.
6. **Best-effort logging still needs diagnostic context.** Non-fatal telemetry
   failures are correct, but generic logs are not useful. Include `turn_id`,
   `startup_id`, `session_id`, `stage`, and model/tool context in log messages.
7. **Double-check transcribed snippets against the real file.** Review caught
   cases where pasted snippets omitted or truncated exactly the setup code that
   mattered. When a test or route body is under review, paste the uncut function.
8. **Validation-status mapping needs an end-to-end test.** It was not enough to
   assume `validate_tool_arguments()` returned `"tool_validation_error"`; the
   test had to exercise the real dispatcher path with schema-invalid arguments.
9. **Keep unrelated untracked files out of phase commits.** The workspace
   contained unrelated `node_modules/` / `package*.json` files. Stage explicit
   paths for the AgentOps commit rather than using a blind `git add .`.

---

## 5. Current Status

- AgentOps schema, models, migration, route-level instrumentation, metrics
  services, alerting service, pricing helper, eval runner, and fixture cases are
  implemented.
- `app/services/orchestrator.py` remains untouched; instrumentation is wired by
  composition in `app/api/routes.py::chat()`.
- Metrics writes use isolated AgentOps sessions and commit independently of the
  student-facing request session.
- Metrics-recording failures are best-effort and non-fatal, with diagnostic log
  context.
- Alerting is deterministic, warning-only, DB-only, and tested with injected
  time/window boundaries.
- Eval suite covers `idea`, `lean_canvas`, and `bmc` with hand-authored JSON
  fixtures, real orchestrator/tool validation, no DB, and no live API key.
- Full AgentOps verification suite is green: 55 tests passed.
- Deferred operational surface remains explicit: no `/agentops/*` endpoints, no
  ops-role auth, no outbound alert delivery, no scheduler, no critical tier, and
  no DB-backed eval history in this phase.
