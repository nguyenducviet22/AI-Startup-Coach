# Hosting Platform

For deployment, AI Startup Coach targets a PaaS provider (Railway, Render, or Fly.io) rather than Azure/AWS/GCP for the current stage of the project.

## Why

The project is a single-developer effort using Codex CLI for implementation and Claude for review, with no dedicated DevOps engineer and no live production traffic yet. Azure/AWS/GCP bring meaningful operational overhead (VNet/networking, IAM/RBAC, Key Vault, CAF naming and tagging, private DNS) that has no corresponding requirement today — no enterprise customer, compliance obligation, or cloud-specific integration is driving the need for a hyperscaler. A PaaS provider covers the stack directly: FastAPI web service, managed PostgreSQL, and Git-push deploys, at lower cost and lower operational burden for a project at this stage.

## What this does not lock in

The backend has no cloud-provider-specific code. `app/llm/openrouter.py` already isolates the LLM provider behind a `ChatCompletionClient` protocol so business logic doesn't depend on any specific SDK; the same separation applies at the infra level — nothing in `app/` assumes Azure, AWS, or any specific PaaS. If the project later needs a hyperscaler (enterprise requirements, compliance, scale), migration is expected to be a hosting change, not an application rewrite.

## Consequence for the DevOps skill (`hs:devops`)

The `azure-terraform-iac.md` reference in `hs:devops` does not apply while this decision holds. The `github-actions-cicd.md` reference still applies (test/lint/security-scan stages are provider-agnostic); only its deploy step targets the chosen PaaS instead of Azure, and its Azure-specific guidance (OIDC via `azure/login@v2`, Terraform-state concurrency) does not apply.

PaaS deploy configuration (e.g. `railway.json`, `render.yaml`, or `fly.toml`) is not covered by `hs:devops`'s gated workflows and has no equivalent hard-gate or confirmation checkpoint. It must be reviewed manually before merge rather than relying on the skill's built-in safeguards.

## Update — 9Router as an additional infrastructure dependency

The project is migrating its LLM provider from OpenRouter (a cloud API, no hosting required) to 9Router (a self-hosted OpenAI-compatible proxy — https://github.com/decolua/9router). Unlike OpenRouter, 9Router is not a hosted cloud service; it is a piece of software the project must run itself. This changes the hosting picture and must be accounted for before finalizing CI/CD (`hs:devops` Stage 1) and PaaS deploy config (`hs:devops` Stage 2).

**What this adds to the hosting plan:**
- 9Router must run as its own deployed service, reachable by the FastAPI backend at a real network address — not `localhost`, which only works for local development. Default local port is `20128`.
- Deployment options: (a) self-host 9Router as a container/service on the same PaaS project (Render/Railway/Fly.io) as the backend, or (b) use a 9Router-hosted VPS offering if one is adopted instead of self-hosting. This project defaults to (a) — self-hosted alongside the backend — unless a specific reason to use a managed VPS offering is documented here later.
- 9Router holds its own set of upstream provider API keys (OpenAI, Anthropic, DeepSeek, etc.) in its own dashboard/config, separate from this project's `.env`. This is a new secret-management surface outside `app/core/config.py` and must be provisioned and rotated independently.
- The backend's `.env` now needs a base URL pointing at the deployed 9Router instance (e.g. `LLM_PROXY_BASE_URL`) plus whatever credential 9Router requires to accept requests from the backend — not the upstream provider keys themselves.

**Consequence for `hs:devops`:**
- Stage 1 (`github-actions-cicd`): the pipeline needs a step (or at minimum a documented manual pre-check) confirming the 9Router service is deployed and reachable before the backend deploy step runs, since the backend now has a runtime dependency that didn't exist under plain OpenRouter.
- Stage 2 (PaaS deploy config): the deploy config must provision 9Router as a service alongside the backend and Postgres (e.g. an additional service block in `render.yaml`, or an additional Railway service in the same project), not just the backend and DB as originally scoped.

**Privacy note:** coaching conversation content (which may include sensitive founder/startup information) will now pass through a self-hosted third-party open-source proxy before reaching the upstream LLM provider. This does not change how OpenRouter was already trusted with the same content, but it does add one more hop under this project's own operational responsibility — worth revisiting if any compliance requirement is added later (see "Revisit when" below).

## Revisit when

- A customer or partner requires a specific cloud provider (compliance, procurement, existing enterprise agreement).
- Traffic/scale exceeds what the chosen PaaS tier comfortably handles.
- A feature requires a cloud-native service with no PaaS equivalent (e.g. VNet-isolated internal services, a specific managed AI/data service).

If any of the above happens, revisit this ADR before running `hs:devops`'s `azure-terraform-iac.md` workflow.