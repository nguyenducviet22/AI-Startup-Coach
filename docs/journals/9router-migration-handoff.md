# 9Router Migration Handoff Note

**Status:** OpenRouter -> 9Router migration complete, reviewed, and verified; ready for shipping.
**Repo:** https://github.com/nguyenducviet22/AI-Startup-Coach
**Scope:** LLM client configuration and provider hop only.

---

## 1. Architecture Overview

```
API routes / AgentOps wrappers
  -> ChatCompletionClient protocol
      -> OpenRouterChatClient (app/llm/openrouter.py)
          -> AsyncOpenAI pointed at LLM_PROXY_BASE_URL (9Router)
          -> configured LLM_PROXY_MODEL
          -> retry/backoff for transient provider failures
```

- `app/llm/openrouter.py` retains the `ChatCompletionClient` protocol boundary,
  but sends requests through the OpenAI-compatible 9Router base URL and uses
  `LLM_PROXY_MODEL` / `LLM_PROXY_MAX_TOKENS`.
- `app/core/config.py` adds the `LLM_PROXY_*` settings, keeps the legacy
  `OPENROUTER_*` settings for rollback compatibility, and validates the
  non-local deployment path.
- `app/services/agentops/instrumented_chat_client.py` records the effective
  proxy model using the same `LLM_PROXY_MODEL` -> `OPENROUTER_MODEL` fallback
  order as the raw client.
- `app/services/orchestrator.py` and `app/services/tool_dispatcher.py` are
  untouched by this migration. Business logic continues to depend only on the
  protocol boundary.

## 2. Key Design Decisions

| Decision | Why |
|---|---|
| **Add `LLM_PROXY_*` alongside `OPENROUTER_*`** | Keeps rollback possible while 9Router is confirmed in deployment. The legacy values remain available as inert/configurable fallbacks rather than being removed in the migration. |
| **Base URL is explicit-or-fail outside local development** | `LLM_PROXY_BASE_URL` defaults to empty. Only `APP_ENV=local` receives `http://localhost:20128/v1`; every non-local environment must provide an explicit URL, preventing accidental localhost or OpenRouter routing. |
| **Legacy API-key/model fallback is retained** | Empty `LLM_PROXY_API_KEY` and `LLM_PROXY_MODEL` can still use configured legacy values during rollback. This does not create a URL fallback, so deployment routing remains explicit. |
| **Reject empty and known placeholder models outside local** | A non-local deployment must not start with either an empty effective model or `replace-with-openrouter-model-slug` / `replace-with-9router-model-id`, which would otherwise be sent directly to 9Router. |
| **Sanitize provider errors** | `LLMProviderError` now exposes the fixed internal code `LLM_PROVIDER_REQUEST_FAILED`; upstream response bodies and diagnostic exception details do not reach logs or the raised error string. |
| **Preserve the protocol boundary** | The orchestrator and dispatcher do not know whether the provider is OpenRouter, 9Router, or another OpenAI-compatible service. |

## 3. Known Technical Debt / TODOs

- `MODEL_PLACEHOLDERS` in `app/core/config.py` duplicates the literal default
  string from the `openrouter_model` field. If that default changes, the set
  must be updated too, or placeholder detection silently stops working.
- Rollback to OpenRouter is no longer as simple as unsetting environment
  variables. In non-local environments, `LLM_PROXY_BASE_URL` and
  `LLM_PROXY_MODEL` must be explicitly set to OpenRouter's values because the
  validator no longer permits an implicit base URL fallback.
- No explicit timeout is configured for the 9Router proxy hop; the client
  currently relies on the OpenAI SDK default.
- The fallback intentionally permits a real `OPENROUTER_MODEL` value when
  `LLM_PROXY_MODEL` is empty. This supports rollback compatibility, but it also
  means an OpenRouter-style slug can reach 9Router unchanged until the proxy
  model is explicitly configured.

## 4. Touchpoints With DevOps

The deployed backend configuration must account for:

- `APP_ENV`
- `LLM_PROXY_BASE_URL`
- `LLM_PROXY_API_KEY`
- `LLM_PROXY_MODEL`
- `LLM_PROXY_MAX_TOKENS`
- `OPENROUTER_API_KEY`
- `OPENROUTER_BASE_URL`
- `OPENROUTER_MODEL`
- `OPENROUTER_MAX_TOKENS`
- `OPENROUTER_HTTP_REFERER`
- `OPENROUTER_X_TITLE`

`APP_ENV != "local"` activates strict validation. DevOps must set this value
correctly in every deployed environment and provide an explicit
`LLM_PROXY_BASE_URL` and real `LLM_PROXY_MODEL`, or the app fails to start by
design. The 9Router credential is supplied through `LLM_PROXY_API_KEY`; the
upstream provider keys belong to 9Router's own deployment/configuration.

## 5. Current Status

- Migration implementation and review rounds are complete.
- `app/services/orchestrator.py` was reverted to zero diff; it is not part of
  the migration.
- `app/services/tool_dispatcher.py` was not modified.
- Focused migration tests passed.
- Full regression suite passed: **176 passed, 13 warnings** in **57.88s**.
- Warnings were non-blocking Alembic deprecation/cache warnings; no tests
  failed or errored in the definitive run.
