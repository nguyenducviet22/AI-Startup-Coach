# Render deployment configuration

This repository includes [`render.yaml`](../render.yaml) for two independently
deployed production services and one Render-managed PostgreSQL database:

- `ai-startup-coach-backend` — Python/FastAPI web service.
- `ai-startup-coach-frontend` — Vite static site.
- `ai-startup-coach-db` — the database wired into the backend as `DATABASE_URL`.

**Release blocker:** this blueprint is not ready to apply until the separate
application CORS follow-up is implemented. The current FastAPI app does not
allow the Render frontend origin; see the tracked follow-up below.

The names and `singapore` region are intentional defaults in the blueprint.
Before applying it, confirm that they match the services you create in the
Render dashboard. Stage 1's `RENDER_BACKEND_DEPLOY_HOOK_URL` and
`RENDER_FRONTEND_DEPLOY_HOOK_URL` secrets are URLs for these exact web services;
the blueprint cannot update an existing hook if a service is renamed, recreated,
moved to another region, or replaced with a different runtime.

## Deployment order and commands

The backend build runs `pip install .`. The repository's `pyproject.toml` places
`alembic`, `asyncpg`, `sqlalchemy[asyncio]`, and `uvicorn[standard]` in the
base `[project].dependencies`, not the optional `[project.optional-dependencies]`
group. Plain `pip install .` therefore installs every command needed by the
start and migration commands; the CI-only `.[dev]` extra is not required at
runtime.

Render then runs the **pre-deploy command** `alembic upgrade head` against the
configured `DATABASE_URL`. This is
the release/migration phase: it must finish successfully before the new web
instance starts with `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
Therefore, the first deploy creates the schema (including all migrations), and
each later deploy applies only pending migrations. A failed migration stops the
release; do not bypass it by manually starting the service against an unknown
schema. Render's pre-deploy command is run for each deploy, so migrations must
remain backward-compatible with the currently running version during rollout.

The frontend uses the same commands as CI: `npm ci && npm run build`, from the
`frontend` root, and serves the resulting `dist` directory as a Render static
site. `VITE_API_BASE_URL` is injected at build time and must be the public HTTPS
URL of the backend, with no trailing slash (for example,
`https://ai-startup-coach-backend.onrender.com`). It is not a secret.

## Environment variables

The backend table is derived from `app/core/config.py::Settings` and
`.env.example`. Values marked `sync: false` in `render.yaml` must be entered in
the Render dashboard; never commit their values.

### Backend (`ai-startup-coach-backend`)

| Variable name | Source | If missing or wrong |
| --- | --- | --- |
| `DATABASE_URL` | Render-injected connection string from `ai-startup-coach-db` | Startup, migrations, and all persistence operations fail. |
| `LLM_PROVIDER` | Set to `9router` | The configured provider is unclear or unsupported. |
| `LLM_API_KEY` | Set directly in the Render dashboard (secret) | LLM requests fail authentication. |
| `LLM_BASE_URL` | Set directly in Render to the 9Router `/v1` endpoint | LLM requests go to an invalid or unintended endpoint. |
| `LLM_MODEL` | Set directly in Render to a real 9Router dashboard model ID | The placeholder is not usable and chat requests fail. |
| `LLM_MAX_TOKENS` | Set directly in Render; default `1024` | Invalid/too-small values can reject requests or truncate responses. |
| `LLM_TIMEOUT_SECONDS` | Set directly in Render; default `30` | Requests can hang too long or time out too quickly. |
| `LLM_SUPPORTS_TOOLS` | Set after confirming the selected model supports tools | Tool calls are omitted when set to `false`; otherwise unsupported-model errors may occur. |
| `LLM_HTTP_REFERER` | Set directly in Render to the public app URL | Optional request attribution is missing or misleading. |
| `LLM_X_TITLE` | Set directly in Render; default `AI Startup Coach` | Optional request attribution is missing or misleading. |
| `CHAT_HISTORY_LIMIT` | Set directly in Render; default `20` | Invalid values can break history retrieval or create excessive context. |
| `LLM_MAX_RETRIES` | Set directly in Render; default `2` | Invalid values can cause unnecessary failures or excessive retries. |
| `LLM_RETRY_BACKOFF_SECONDS` | Set directly in Render; default `1.0` | Invalid values can make retry storms or immediate repeated failures. |
| `AGENTOPS_PRICING_ENABLED` | Set directly in Render; default `true` | Pricing metrics are disabled/enabled unexpectedly. |
| `JWT_SECRET` | Set directly in Render (long random secret; secret) | The required Settings object cannot initialize, or tokens cannot be trusted. **Never reuse this value across environments and never commit it.** |
| `JWT_ALGORITHM` | Set directly in Render; default `HS256` | Tokens may fail validation or use an unintended algorithm. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Set directly in Render; default `30` | Tokens may expire immediately or remain valid too long. |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Set directly in Render; default `7` | Refresh sessions may expire immediately or remain valid too long. |

### Frontend (`ai-startup-coach-frontend`)

| Variable name | Source | If missing or wrong |
| --- | --- | --- |
| `VITE_API_BASE_URL` | Set directly in the Render dashboard at build time; public backend URL | The browser calls the static site's origin or the wrong API and authentication/data requests fail. |

## PostgreSQL provisioning and migration policy

This blueprint assumes **Render managed PostgreSQL**, rather than an external
provider, because Render can inject the private connection string directly into
the backend service and keep the database in the same region. The database is
named `ai-startup-coach-db`; `DATABASE_URL` is wired with `fromDatabase` and must
not be copied into GitHub secrets or committed to the repository.

Render exposes internal and external connection details in the database
dashboard. If credentials are rotated in Render, the injected connection string
changes with the database credentials; restart/redeploy the backend so its
environment is refreshed, then verify `alembic upgrade head` and `/health`.
Coordinate rotation during a maintenance window because old running instances
cannot use a connection string that has already been revoked.

The initial migration executes `CREATE EXTENSION IF NOT EXISTS pgcrypto`. Render
documents `pgcrypto` as a supported extension for Render Postgres; on PostgreSQL
13 and later supported extensions are available through `CREATE EXTENSION`.
This blueprint therefore uses a current Render Postgres plan, but the operator
must still verify the selected database's PostgreSQL major version and extension
allow-list in the dashboard before first production deploy. If the database is
PostgreSQL 11/12, Render enables its supported extensions by default; do not
assume an unlisted extension is available.

## Required manual checks and tracked application follow-up

Before applying the blueprint:

1. Create/confirm both web services and the managed database, matching the
   names, region, and runtimes above.
2. Enter every `sync: false` backend value, choose a real
   `LLM_MODEL`, generate a unique production `JWT_SECRET`, and set the
   frontend `VITE_API_BASE_URL` to the backend HTTPS URL.
3. Confirm the backend deploy hook in
   `RENDER_BACKEND_DEPLOY_HOOK_URL` and frontend deploy hook in
   `RENDER_FRONTEND_DEPLOY_HOOK_URL` point to these exact services.
4. Confirm `autoDeploy: false` remains set for both services. GitHub Actions is
   the only production deploy trigger in Stage 1; the declaration is also
   present in `render.yaml` so a later Blueprint sync does not silently restore
   native deploys.
5. Confirm the database is reachable and `pgcrypto` is permitted before the
   first migration run.

### Tracked follow-up: production CORS configuration

The current FastAPI application does not add `CORSMiddleware`. Because the
frontend and backend are separate origins on Render, browser requests will be
blocked by CORS even when `VITE_API_BASE_URL` is correct. Add an explicit
production frontend-origin CORS configuration in `app/main.py` (or the
application's governing API configuration) before launch, with tests covering
the deployed origin. This is an application-code change outside this
configuration-only stage; do not treat this Blueprint as ready to apply until
that follow-up ships.

## JWT secret choice

`JWT_SECRET` deliberately uses `sync: false` rather than `generateValue: true`.
This keeps generation and rotation under the operator's explicit control while
still keeping the value out of source control. Generate a unique, high-entropy
production value, never reuse it in another environment, and rotate it through
a planned maintenance procedure because rotation invalidates existing tokens.
