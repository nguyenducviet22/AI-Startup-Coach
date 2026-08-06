# Research Agent Data Source

**Status:** Proposed
**Date:** 2026-08-06

For the Research Agent's first pass, AI Startup Coach will use **Tavily Search
and Tavily Extract** behind a provider-neutral `ResearchProvider` protocol.
Basic search, bounded results, no provider-generated answer, and basic
extraction are the defaults. Provider-specific output is normalized into the
product's own cited-evidence schema before it reaches coaching logic or the
founder.

## Why

The feature needs both open-web discovery and extraction from URLs supplied by
the founder. It also requires direct source URLs, freshness controls, bounded
evidence content, and predictable per-call cost.

Public pricing and service status were verified on 2026-08-06:

| Candidate | Cost and capability | Decision rationale |
|---|---|---|
| **Tavily** | 1,000 free credits/month; $0.008/credit pay-as-you-go. Basic search is 1 credit, advanced search is 2, and basic extraction is 1 credit per 5 successfully extracted URLs. Search returns source URLs/content and supports news, date, and domain filters; Extract handles founder-supplied pages. | Chosen because one provider covers the complete first-pass search/extract path and returns LLM-ready, directly attributable evidence at a predictable low-volume cost. |
| **Exa** | Search is $7/1,000 requests for up to 10 results; deep search is $12–$15/1,000, with additional content/summary charges. It returns URLs, publication dates, highlights, filters, and structured grounding. | Technically strong and slightly cheaper for base search, but its public standard terms restrict distributing/publishing information obtained through the service unless separately permitted. Use would require a suitable written agreement. |
| **SerpApi** | 250 free searches/month; listed paid tiers are $25/1,000, $75/5,000, $150/15,000, and $275/30,000. It supplies real-time structured SERPs/direct links, a one-hour cache, and a 99.95% SLA. | Strong raw search reliability, but low-volume pricing is higher and equivalent page extraction needs a second provider/layer. Its legal shield concerns collection and does not transfer responsibility for downstream use. |
| **Google Custom Search JSON API** | Existing customers get 100 queries/day free and then pay $5/1,000. | Rejected because it is unavailable to new customers and ends for existing customers on 2027-01-01. |
| **Bing Search APIs** | Retired. | Rejected because Microsoft decommissioned the product on 2025-08-11. Azure Agent grounding is a different agent-runtime dependency, not a drop-in search API for this architecture. |

Official sources:

- [Tavily pricing](https://docs.tavily.com/documentation/api-credits),
  [Search API](https://docs.tavily.com/documentation/api-reference/endpoint/search),
  [Extract API](https://docs.tavily.com/documentation/api-reference/endpoint/extract),
  and [terms](https://www.tavily.com/terms)
- [Exa pricing](https://exa.ai/pricing),
  [Search API](https://exa.ai/docs/reference/search), and
  [terms](https://exa.ai/assets/Exa_Labs_Terms_of_Service.pdf)
- [SerpApi pricing](https://serpapi.com/pricing),
  [Search API](https://serpapi.com/search-api), and
  [legal terms](https://serpapi.com/legal)
- [Google Custom Search JSON API status and pricing](https://developers.google.com/custom-search/v1/overview)
- [Microsoft Bing Search API retirement](https://learn.microsoft.com/en-us/lifecycle/announcements/bing-search-api-retirement)

Tavily is not treated as the authority for a claim. The application retains and
shows the underlying page URL, the actual UTC retrieval time, any available
publication time, and only bounded evidence excerpts/attributed paraphrases.
Provider-generated answers are disabled in the normal path. Laws/regulations
require official jurisdictional sources; industry statistics require the
original publisher and measurement context when available.

The standard terms place responsibility for verification and third-party rights
on the customer and contain broad processing rights for inputs/outputs. Public
production is therefore gated on written confirmation or an order form/DPA that
expressly permits founder-facing attributed results and provides acceptable
retention/training treatment. This is a commercial/legal validation gate, not a
deferral of the technical provider decision. The product will not redistribute
full page content.

## What this does not lock in

The orchestrator, tool dispatcher, quota/cache services, evidence schema,
legal-warning contract, and AgentOps records do not depend on Tavily's SDK or
response shape. Business logic depends only on `ResearchProvider`. A different
provider can replace Tavily without changing the stage machine or
founder-facing citation contract.

This ADR does not lock in Tavily Research, Tavily-generated answers, advanced
search as the default, multi-provider aggregation, global caching, or a
long-lived content corpus. It also grants no right to republish third-party page
content beyond attributed, bounded evidence allowed by applicable terms and
law.

## Revisit when

- Tavily will not confirm founder-facing commercial display or acceptable
  retention/training terms before production launch.
- Citation URL validity, extraction success, freshness, or answer-grounding
  evaluations fail the acceptance threshold agreed during `hs:plan`.
- Search volume makes a different provider materially cheaper after accounting
  for extraction and failure rates, not just headline search price.
- The product needs contractual SLA, zero-data-retention, data residency, DPA,
  regulated-data, or enterprise indemnity terms unavailable on the selected
  plan.
- The feature needs specialist sources (paid market data, patents, academic
  indexes, legal databases, or authenticated sites) that open-web search cannot
  support reliably.
- Provider terms, pricing, API availability, or redistribution rules materially
  change.
