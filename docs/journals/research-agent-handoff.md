# Research Agent Handoff Note

**Status:** Research Agent complete, reviewed checkpoint-by-checkpoint, and ready for the next phase.
**Repo:** https://github.com/nguyenducviet22/AI-Startup-Coach
**Full plan:** `docs/research-agent-plan.md`
**Design record:** `docs/research-agent-brainstorm.md` and `docs/adr/research-agent-data-source.md`

---

## 1. Architecture Overview

```
Chat route
  -> route-created ResearchExecutionContext
  -> ToolDispatcher.research_web
  -> InstrumentedResearchService
  -> ResearchService
      -> ResearchCacheService
      -> ResearchQuotaService
      -> ResearchProvider (Tavily adapter)

Standalone founder endpoint
  -> InstrumentedResearchService (turn_id=None)
  -> same ResearchService / cache / quota / provider path
```

The Research Agent has two owner-protected entry points: the stage-gated
`research_web` tool in chat, and `POST /startups/{startup_id}/research` for a
founder-initiated search or URL extraction. Both compose the same
`ResearchService`, which owns request validation, per-startup cache behavior,
quota reservation/reconciliation, provider dispatch, and normalized evidence.
`ResearchProvider` isolates the rest of the application from Tavily; only the
adapter knows Tavily HTTP shapes.

`InstrumentedResearchService` wraps the shared service at the route-level
composition seam. It writes one best-effort `research_calls` AgentOps record
after the correctness-critical provider/quota/cache work completes. Chat calls
use the route-created `turn_id`; the standalone endpoint deliberately writes a
nullable `turn_id` because it does not execute `handle_turn()`.

The response policy runs outside the unchanged orchestrator. It validates
citations against current-turn evidence and persisted research evidence from
earlier assistant turns in the same chat session, adds the legal notice when
needed, and replaces unsupported factual synthesis with the uncertainty
message. The deterministic eval runner exercises the real tool schema, stage
gate, orchestrator, and response policy with fixture-backed provider results.

---

## 2. Key Design Decisions

| Decision | Why |
|---|---|
| **Tavily Search + Extract behind `ResearchProvider`** | Tavily is the selected v1 source because it supports web search and founder-supplied URL extraction. Application-facing schemas are provider-neutral, and no SDK/HTTP response leaks outside `app/research/tavily.py`. |
| **Two-turn research-to-generation flow** | A generation tool in the same LLM tool-call batch cannot see a preceding research result. Research happens in one turn; document generation happens in a later turn. Same-turn batches are never labelled research-informed. |
| **Per-startup cache partitioning** | Cache keys and cache reads are scoped by `startup_id`; there is no global cache reuse between founders. Category-sensitive TTLs protect freshness while retaining the original `retrieved_at` on cache hits. |
| **Correctness-critical quota reservation** | `ResearchQuotaService` takes deterministic, transaction-scoped advisory locks and reconciles actual provider credits. Cache hits reserve nothing; provider failures release unbilled reservations. |
| **AgentOps by composition, not inside `ResearchService`** | Quota/cache correctness uses the request path. Cost, latency, cache and provider-attempt telemetry use isolated best-effort AgentOps sessions in `InstrumentedResearchService`, so telemetry failure cannot change a founder response. |
| **Structured evidence and enforced citation policy** | Evidence has source IDs, direct URLs, bounded excerpts, and preserved UTC retrieval timestamps. Legal evidence carries the mandatory notice; unsupported prose is rewritten rather than presented as settled fact. |
| **Cross-turn same-session citation lookup** | A later generation can cite evidence from an earlier research turn in the same session through persisted assistant `tool_call_data`. This was added during code review so the production behavior matches the approved two-turn flow. |
| **No document provenance foreign key in v1** | Research remains represented in chat content, responses, and AgentOps records. Existing versioned document tables retain their atomic `version`/`is_current` behavior without a research linkage. |

---

## 3. Known Technical Debt / TODOs

- **Cross-turn citation freshness is unbounded.** See the existing [Research
  Agent cross-turn citation freshness entry](agentops-handoff.md#3-known-technical-debt--todos).
  Cache expiry governs reuse for a new provider call, not whether already
  surfaced evidence may be cited later. Freshness-sensitive categories need a
  maximum-age policy or a visible stale-evidence marker in a future scope.
- **Tavily commercial terms/DPA confirmation is a production launch gate.** Do
  not treat code completion as authorization to launch publicly. Obtain written
  confirmation/order-form or DPA coverage for founder-facing attributed output
  and acceptable input/output retention and training treatment before launch.
- **First-pass scope remains deliberately bounded.** No autonomous background
  research, scheduled monitoring/news feed, multi-provider fallback or voting,
  cross-session research library/RAG corpus, authenticated/paywalled scraping,
  bulk/full-page redistribution, specialist data integrations, dedicated
  research notebook/report generation, AgentOps dashboard/billing UI, quota
  add-ons, or outbound cost alerts is included.
- **No new research-source quality model.** Authority classifications are
  deterministic metadata, not an automated assessment of truth or legal
  compliance. Founder-visible results remain evidence, not advice.

---

## 4. Pitfalls Observed This Phase

1. **An eval can accidentally validate a different policy from production.**
   The initial two-turn eval checked citations with eval-only logic, so it could
   have passed while `research_response_policy.py` rejected an otherwise valid
   citation to a prior research turn. The runner now calls the production
   policy, and the policy receives same-session prior research tool data.
2. **Provider failures are not always pre-provider failures.** A timeout means
   Tavily was attempted even when no result was received. `provider_call_made`
   must be derived from the reviewed provider-attempt error-code contract, not
   assumed false for every failed invocation.
3. **Migration verification needs both directions.** An upgrade-only test did
   not prove that the three research tables and their constraints could be
   removed safely. The live-Postgres migration test now covers head upgrade and
   downgrade to the previous revision.
4. **Concurrency claims need real overlap.** Quota/cache tests use overlapping
   tasks and synchronization barriers against Postgres; sequential awaits are
   not evidence that advisory-lock or upsert behavior is race-safe.
5. **A URL-only request is a first-class request.** The shared request schema
   must validate query-or-URL rather than routing a synthetic query string into
   cache keys, fingerprints, prompts, or audit data.

---

## 5. Current Status

- Checkpoints 0 through 6 are implemented and approved.
- The Alembic chain is linear through `20260806_0006`; research schema upgrade
  and downgrade are exercised against live Postgres.
- Fresh final verification: backend `pytest` passed **268 tests**; Ruff passed;
  deterministic evals passed **4/4** fixtures; frontend lint, typecheck, test
  (**56 tests**), and production build passed.
- `app/services/orchestrator.py` remains unchanged; Research Agent behavior is
  wired through route-level composition and response-policy helpers.
- The feature is ready for the next phase, subject to the production launch
  gate for Tavily commercial terms/DPA confirmation documented above.
