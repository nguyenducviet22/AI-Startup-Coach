# Research Agent — Brainstorm Decision Document

**Status:** Proposed for review; this document completes `hs:brainstorm` only.
**Date:** 2026-08-06
**Decision boundary:** No implementation plan or implementation code is authorized by this document.

## 1. Problem and binding design constraints

AI Startup Coach needs current external evidence for market sizing, adoption,
competitors, pricing, trends, regulation, industry statistics, research, news,
and founder-supplied web pages. Research is useful only when a founder can see
where a claim came from and when it was retrieved. The feature therefore treats
grounding as part of the data contract, not as a writing preference left to the
LLM.

The existing architecture remains authoritative:

- A provider-specific SDK must stay behind a `ResearchProvider` protocol. The
  orchestrator, dispatcher, and business services must not import it.
- `app/services/orchestrator.py` remains unmodified. Research is added through
  the existing tool/dispatcher path and route-level composition precedent used
  by AgentOps.
- All provider keys, limits, cache TTLs, and pricing controls have one source of
  truth in `Settings`; they are not repeated as service-local defaults.
- All startup-scoped paths first enforce the existing
  `require_startup_owner()` non-leaking ownership boundary.
- Service failures cross boundaries only as the project's structured error
  shapes. Provider exceptions and response bodies are never exposed raw.
- Every ordering-sensitive research/audit table uses a monotonic `sequence`
  identity in addition to timestamps.

### Hard grounding rule

Every research result surfaced to a founder **must include a source URL and the
UTC date/time at which that source was retrieved**. Every research-derived
claim in coaching prose must cite one or more returned source records. The
coaching agent must never present an unsourced or unverifiable claim as settled
fact; it must omit it or label it explicitly as an estimate, hypothesis, or
unverified statement.

This rule shapes both sides of the boundary:

- The research result schema carries stable `source_id`, `url`, `title`,
  `retrieved_at`, optional `published_at`, a bounded evidence excerpt, and an
  authority classification. Synthesized claims carry `source_ids` rather than
  free-floating citation text.
- Research-aware prompt policy is composed into every applicable stage prompt.
  It instructs the model to cite source URLs with retrieval dates, preserve
  uncertainty, and never treat the provider's ranking or generated summary as
  proof by itself. This composition must not add a research branch to
  `AgentOrchestrator.handle_turn()`.

Laws/regulations and industry statistics receive the strictest treatment:

- A legal or regulatory obligation may be stated as verified only when an
  official government, legislature, court, or regulator source for the named
  jurisdiction supports it. Secondary sources may explain but cannot establish
  the obligation. If jurisdiction or effective date is unclear, the result is
  explicitly unresolved.
- An industry statistic must identify the original publisher, measurement
  period, and methodology/sample when the source provides them. A secondary
  article quoting an inaccessible report is not enough to present the number as
  settled fact; it is labeled a secondary estimate.
- Provider-generated answers are disabled for the normal search path. The
  system grounds against returned source pages/snippets and retains the direct
  URLs.

## 2. Decision 1 — Search and data provider

### Options considered

Pricing and availability below were verified against official provider pages
on 2026-08-06. Dollar figures are public list prices and can change.

| Provider | Public cost | Citation/source fit and freshness | Redistribution/licensing concern | Decision |
|---|---:|---|---|---|
| **Tavily** | 1,000 credits/month free; pay-as-you-go is $0.008/credit. Basic search costs 1 credit and advanced search 2, or about $8/$16 per 1,000 calls. Basic extraction charges 1 credit per 5 successful URLs. | Search returns a direct URL, title, bounded content, request ID, and usage. It supports news, relative/absolute date filters, domain filters, and extraction of founder-supplied URLs. News results can include publication dates. This is the closest fit to an LLM tool without a second scraping provider. | The standard terms expressly contemplate Customer Application integration and distribution/publication of output after customer verification, but make the customer responsible for third-party rights and contain broad input/output processing language. Only bounded attributed excerpts and paraphrases may be shown; full-page redistribution is prohibited by product policy. Written commercial-use confirmation is a launch gate. | **Chosen for v1.** |
| **Exa** | Search is $7/1,000 requests for up to 10 results; deep search is $12–$15/1,000, with separate content/summary charges. | Strong structured metadata: direct URLs, publication dates, highlights, date/domain filters, publication/news categories, and optional field-level grounding. Good semantic discovery and research-paper support. | The public standard terms prohibit copying, distributing, publishing, or creating derivatives from information obtained through the service unless expressly permitted in the terms or in writing. That is a poor default for founder-facing results without a negotiated agreement. | Rejected for the standard-plan first pass; viable under a suitable written agreement. |
| **SerpApi** | Free 250/month; $25/1,000, $75/5,000, $150/15,000, and $275/30,000. Effective price ranges from $25 to about $9.17 per 1,000 at listed tiers. | Mature real-time structured SERP results with direct links, broad search-engine coverage, a one-hour provider cache, and a published 99.95% SLA. It is strong for competitor/search visibility, but page content extraction and LLM-ready evidence require another fetch/extract layer. | Terms put downstream legality and third-party rights on the customer. The legal shield covers collection, not the application's use of the data, and the governing terms exclude Free, Starter, and Developer tiers from that shield despite shorter pricing-page labels. | Rejected for v1 because it is more expensive at low volume and does not cover the full supplied-URL/extraction use case alone. |
| **Google Custom Search JSON API** | Existing customers receive 100 queries/day free, then $5/1,000 up to 10,000/day. | Direct Google result URLs and fresh index quality, but it is a result API rather than a complete evidence-extraction path. | It is unavailable to new customers and all existing access ends 2027-01-01. Product-specific display/attribution rules would also apply. | Rejected: not procurable or durable for a new feature. |
| **Bing Search APIs** | Not applicable. | Historically returned current web results and URLs. | Microsoft retired the APIs on 2025-08-11 and directs customers to Azure AI Agent grounding, which would couple this product to a different agent runtime. | Rejected: unavailable. |

Official references:

- [Tavily credits and pricing](https://docs.tavily.com/documentation/api-credits)
- [Tavily Search API](https://docs.tavily.com/documentation/api-reference/endpoint/search)
- [Tavily Extract API](https://docs.tavily.com/documentation/api-reference/endpoint/extract)
- [Tavily platform terms](https://www.tavily.com/terms)
- [Exa pricing](https://exa.ai/pricing)
- [Exa Search API](https://exa.ai/docs/reference/search)
- [Exa terms](https://exa.ai/assets/Exa_Labs_Terms_of_Service.pdf)
- [SerpApi pricing](https://serpapi.com/pricing)
- [SerpApi API behavior](https://serpapi.com/search-api)
- [SerpApi legal terms](https://serpapi.com/legal)
- [Google Custom Search JSON API status and pricing](https://developers.google.com/custom-search/v1/overview)
- [Microsoft Bing Search API retirement](https://learn.microsoft.com/en-us/lifecycle/announcements/bing-search-api-retirement)

### Chosen answer

Use **Tavily Search plus Tavily Extract for the first pass**, behind a
provider-neutral `ResearchProvider` protocol. Use deterministic provider
adapters to normalize Tavily output into the product's own evidence schema;
neither prompts nor founder-facing API shapes contain Tavily-specific fields.
Default to basic search, a bounded result count, no Tavily-generated answer,
and basic extraction. Advanced search is allowed only when the request declares
the higher estimated credit cost before quota reservation.

This decision does not authorize copying entire pages or presenting Tavily's
generated text as the application's own verified conclusion. The product shows
short evidence excerpts, attributed paraphrases, direct links, retrieval dates,
and any available publication dates. The separate ADR is at
`docs/adr/research-agent-data-source.md`.

## 3. Decision 2 — Cost control and AgentOps accounting

### Options considered

1. **Route-only in-memory limiting.** Cheap to build, but internal tool calls
   bypass route-only rules, multiple app instances disagree, and restarts erase
   counters. Rejected.
2. **Provider dashboard limits only.** Useful as a final account-wide circuit
   breaker, but cannot enforce per-user/per-session fairness or return a useful
   structured product error. Rejected as the primary control.
3. **Database-backed reservation at the shared research service boundary.** It
   works for tool and standalone entry points, survives multiple instances, and
   can reserve estimated credits before a call then reconcile actual usage.
   Chosen.

### Chosen answer

All cache misses pass through a shared `ResearchQuotaService` immediately before
the provider call. Authentication and startup ownership have already been
resolved by then, but enforcement is not placed only in the HTTP route because
agent tool calls use the same service directly.

Initial default limits, all configurable only through `Settings`, are:

| Scope | Rolling one-hour limit | Rolling 24-hour limit |
|---|---:|---:|
| Per chat/research session | 8 uncached provider calls | 20 provider credits |
| Per authenticated user, across startups/sessions | 20 uncached provider calls | 60 provider credits |

Both scopes must pass. Calls are reserved atomically before dispatch so
concurrent requests cannot overspend. The hourly call counter includes attempted
external calls to stop retry storms. The daily credit budget reserves the
documented maximum for the selected operation and reconciles to provider-
reported usage afterward; a confirmed unbilled failure releases only the credit
reservation, not the call count. Cache hits use neither allowance. Exhaustion
returns a structured `research_rate_limited` error with scope and retry time,
never a raw provider error.

At Tavily's current pay-as-you-go rate, the user daily default caps billed
search credit exposure at about $0.48 for basic-credit usage or the equivalent
mix of advanced/extract usage. A provider-account monthly spend ceiling remains
enabled as a defense-in-depth circuit breaker.

AgentOps uses a **new `research_calls` table**, not `llm_calls` and not an
`llm_calls`-shaped reuse. Search billing units, cache outcomes, provider request
IDs, and error classes are materially different from tokens/models. Each
research-service invocation records an append-only row with a monotonic
`sequence`; `turn_id` follows the existing join pattern and is nullable only for
standalone requests. Records include startup/session/user scope, provider and
operation, a non-reversible query fingerprint rather than raw sensitive query
text, provider call/cache status, credits reserved and charged, computed
`cost_usd`, `pricing_unknown`, latency, status, structured error code, and
timestamps. Cache hits are recorded with `provider_call_made=false`,
`credits_charged=0`, and an explicit `cache_hit` status—never silently folded
into a zero-cost provider call.

Research pricing follows the explicit AgentOps pricing-table pattern. Provider,
operation, and credit prices are versioned in code and guarded by Settings;
unknown pricing yields `cost_usd=null` and `pricing_unknown=true`, never a
silent zero. Telemetry remains best-effort and isolated from the founder-facing
transaction, while quota enforcement is correctness-critical and therefore not
best-effort.

## 4. Decision 3 — Grounding and citations

### Options considered

1. **Prompt-only citation instructions.** Flexible but unenforceable: the model
   can omit, invent, or detach citations. Rejected.
2. **Schema-only evidence with no prompt rule.** Preserves sources, but the
   coaching response can still state unsupported claims. Rejected.
3. **Schema-enforced evidence plus composed prompt policy and deterministic
   founder-facing rendering.** Chosen.

### Chosen answer

The hard grounding rule in section 1 is mandatory. Research results are a
structured part of the chat/standalone response, not only text buried in a tool
message. The UI renders source title, direct URL, original `retrieved_at`, and
optional `published_at` from that structure. The model may summarize the
evidence, but it cannot manufacture a source record because only normalized
provider results receive source IDs.

For prose, each factual research-derived statement uses inline source markers
that resolve to the structured records. If a response contains a quantitative,
comparative, current-event, legal, or regulatory factual claim without a valid
source ID, that claim is removed or rewritten as unverified before it is
surfaced. This is a deterministic response-policy check around the orchestration
result, composed outside `orchestrator.py`; the prompt is an additional control,
not the sole control.

## 5. Decision 4 — Legal and regulatory handling

### Options considered

1. **Prompt instruction only.** The model can omit or soften the warning.
   Rejected.
2. **Tool/result schema enforcement only.** Guarantees metadata exists, but a
   plain-text client could still fail to display it. Insufficient alone.
3. **Schema-enforced classification and notice, plus unconditional UI/API
   rendering.** Chosen. Prompt reinforcement remains defense in depth.

### Chosen answer

Legal/regulatory classification is performed at the research service boundary.
Any result or claim touching laws, regulations, licensing, compliance, court
decisions, or regulator guidance carries `legal_or_regulatory=true`, the named
jurisdiction if known, source-authority metadata, and this non-optional notice:

> This is not legal advice. Laws and regulations change and vary by
> jurisdiction. Verify the cited primary sources and consult a qualified legal
> professional before acting.

The notice is part of the structured tool/API result and is always rendered by
the founder-facing research component. It is not a string the LLM is asked to
remember. The response policy also requires the same visible framing when legal
content appears in coaching prose. A result without an official primary source
cannot be labeled verified legal guidance; it is returned as secondary
commentary or an unresolved research gap.

## 6. Decision 5 — Integration with the stage machine

### Options considered

1. **Stage-gated agent tool only.** Fits the current dispatcher but makes the
   founder depend on the model deciding to search and gives no direct research
   control. Rejected as incomplete.
2. **Standalone startup endpoint only.** Gives founders control but prevents the
   coach from gathering evidence while producing stage documents. Rejected.
3. **Both entry points over one service and result contract.** Chosen.

### Chosen answer

Research has two entry points:

- A `research_web` tool follows the exact `stage_tools.py` and
  `ToolDispatcher.execute()` allow-list/validation pattern. It is available in
  `idea`, `lean_canvas`, `bmc`, `swot`, `product_plan`, `marketing`, and
  `funding`. It is excluded from `completed`, preserving that stage's existing
  no-tool agent behavior.
- An authenticated, startup-scoped founder-triggered research endpoint remains
  available independently of the current stage, including `completed`. It uses
  `require_startup_owner()` and is associated with an existing or newly created
  startup chat session for quota and AgentOps correlation, but it does not
  mutate stage or document state.

Idea is included because problem validation, market existence, alternative
solutions, and regulatory feasibility are highest-leverage before a canvas is
committed. No coaching stage is excluded: Lean Canvas/BMC need market and
competitor evidence; SWOT needs external opportunities/threats; Product Plan
needs technical/regulatory constraints; Marketing needs channels, benchmarks,
and pricing; Funding needs market size, comparables, and current investor-facing
facts. `completed` excludes only autonomous agent access because its existing
tool set is empty; explicit founder research remains safe and useful.

Both entry points invoke the same startup-scoped `ResearchService`, provider
protocol, quota service, cache, evidence normalizer, legal classifier, and
founder-facing result schema. Neither entry point can bypass grounding,
citation, legal framing, or AgentOps recording.

## 7. Decision 6 — Caching

### Options considered

1. **No cache.** Freshest behavior but repeats billed calls for retries,
   refreshes, and semantically identical stage questions. Rejected.
2. **Global cache keyed only by normalized query.** Maximizes savings but can
   reveal that another startup searched a sensitive market, and personalization
   can contaminate results across founders. Rejected.
3. **Per-startup cache with category-sensitive short TTLs.** Chosen.

### Chosen answer

The cache is database-backed and strictly partitioned by `startup_id`; there is
no global cross-startup result reuse. Ownership is checked before cache lookup.
This intentionally gives up some savings to preserve the privacy boundary for
sensitive founder/startup context.

The cache key is a versioned hash over:

`startup_id + provider + operation + normalized query-or-canonical-URL + locale
+ topic + date range + requested domains + result limit + search depth +
authority/legal mode + normalizer schema version`.

Normalization trims/collapses whitespace and canonicalizes case only where
semantics are case-insensitive; it does not remove meaningful market,
jurisdiction, currency, or date qualifiers. Raw sensitive queries are not put
in logs or cache indexes, although encrypted/controlled cache payload storage
must retain the query/result needed to serve the owning startup.

TTLs are concrete and configurable only through `Settings`:

- **1 hour:** news/current-events, competitor pricing, and legal/regulatory
  searches.
- **6 hours:** general market, trends, industry statistics, research findings,
  competitor profiles, and founder-supplied URL extraction.

An explicit founder “refresh” bypasses cache but still consumes quota. Expired
entries are never presented as fresh and there is no stale-if-error behavior for
legal, pricing, news, or statistics in v1.

A cached result preserves the original `retrieved_at`; it also reports
`served_at` and `cache_hit=true`. Serving from cache must never replace the
retrieval date with “now.” Thus the exact same citation remains honest about
when the page was actually fetched.

## 8. Open questions and launch gates

There are no unresolved architecture choices among the six required decisions.
Two external/product facts cannot be established from repository context and
must remain visible rather than being silently assumed:

1. **Tavily commercial terms confirmation — production launch gate.** Tavily's
   current standard terms contemplate Customer Applications and downstream use
   of verified output, but the service grant also uses “internal business
   purposes” language and grants broad rights to process inputs/outputs. Before
   public production, obtain written confirmation or an order form/DPA that
   expressly permits founder-facing attributed results and establishes
   acceptable retention/training treatment. If Tavily will not provide it,
   revisit the provider ADR; the fallback is SerpApi Production plus a separate
   licensed extraction provider, or Exa under a negotiated redistribution/ZDR
   agreement—not an unreviewed switch.
2. **Jurisdiction is request data, not a global default.** Legal research must
   require the founder/agent to name the applicable country/state/region. The
   product must not silently assume Vietnam, the United States, or the user's
   network location.

## 9. First-pass scope boundary

The first pass includes synchronous on-demand search/extraction, the two entry
points, per-startup short-lived caching, deterministic citations/legal notices,
quota enforcement, and research-call AgentOps accounting.

The following are explicitly out of scope:

- autonomous background research, scheduled monitoring, alerts, or news feeds;
- multi-provider fan-out, automatic provider fallback, or answer voting;
- a long-lived cross-session research library, vector index, embeddings, or RAG
  corpus built from fetched pages;
- paywalled, authenticated, private, or anti-bot-bypassed content;
- full-page/content redistribution, bulk crawling, or storing complete web
  pages beyond the short cache window;
- legal advice, compliance certification, filing guidance, or a determination
  that a startup is legally compliant;
- purchasing proprietary market reports or resolving facts hidden behind an
  inaccessible primary source;
- image, video, social-network, patent, academic-library, or company-database
  specialist integrations;
- a dedicated research notebook/report generator or autonomous source-quality
  scoring model;
- an AgentOps dashboard, billing UI, user-purchased quota add-ons, or outbound
  cost alerts;
- changing stage-transition rules, document versioning behavior, or
  `AgentOrchestrator.handle_turn()`.

Approval of this document should lead to a separate `hs:plan` session. It does
not itself authorize planning or implementation.
