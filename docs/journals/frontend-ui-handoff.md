# Frontend/UI Handoff

## Architecture Overview

The Frontend/UI phase added a React + Vite + TypeScript app under `frontend/`.
It is a single-page app that talks to the existing FastAPI backend and the auth
layer added in the previous phase.

Main pieces:

- `frontend/src/App.tsx` owns auth bootstrapping and top-level routing between
  auth screens and the authenticated workspace.
- `frontend/src/pages/LoginPage.tsx` and `frontend/src/pages/SignupPage.tsx`
  handle auth forms with local submit state.
- `frontend/src/components/AppShell.tsx` is the authenticated workspace shell.
  It loads startups, creates startups, selects the active startup, wires stage
  mutations, opens document tabs, and hosts chat.
- `frontend/src/features/stages/*` renders the coaching stage stepper and
  manual stage controls.
- `frontend/src/features/chat/*` renders chat history, sends chat turns, and
  shows the stage-readiness confirmation prompt.
- `frontend/src/features/documents/*` renders generated documents and version
  history with purpose-built layouts per document type.
- `frontend/src/api/*` contains typed API wrappers and the shared fetch client.
- `frontend/src/stores/authStore.ts` stores auth status/user in Zustand.
- `frontend/src/stores/chatSessionStore.ts` stores the active chat session ID
  per startup for the current tab.

Auth token handling:

- Access token is memory-only in `frontend/src/api/client.ts`.
- Refresh token is stored in `sessionStorage`.
- Closing the tab/browser logs the user out for v1.
- On app boot, `authStore.bootstrap()` attempts silent refresh from
  `sessionStorage` before rendering login.
- On any mid-session 401, `apiRequest()` attempts refresh and retries once.
- If refresh fails at boot or mid-session, the client clears tokens and notifies
  the auth store through `onAuthFailure`, causing the UI to route to login.
- `logout()` clears both memory access token and `sessionStorage` refresh token
  before/while calling the backend logout endpoint.

Backend touchpoints added for the UI:

- `GET /startups` lists the current user's startups newest-first with
  deterministic ordering: `created_at DESC, id DESC`.
- `ChatResponse.stage_readiness` exposes
  `{ ready: boolean, missing_fields: string[] } | null`.
- `GET /startups/{id}/chat/messages?session_id=&limit=&before_sequence=`
  hydrates chat history using user/assistant messages only, sorted by sequence.

Chat behavior:

- Chat is non-streaming in v1. The POST `/startups/{id}/chat` call returns the
  assistant response synchronously.
- The chat panel uses the history endpoint as the single source of truth.
- No optimistic local message copy is kept, to avoid duplicate messages when a
  new `session_id` appears after the first send.
- On send success, the app stores the returned `session_id` and invalidates the
  exact chat-history query so the persisted exchange is fetched back.
- The submit button shows `Sending...` while the request is in flight. There can
  be a brief gap after the mutation resolves and before the history refetch
  paints the new exchange; this was accepted for v1 correctness.

Document behavior:

- Six tabs are always browsable: Lean Canvas, BMC, SWOT, Product Plan,
  Marketing, Funding.
- Tabs are not restricted by current stage. This lets students preview upcoming
  frameworks and revisit earlier work.
- Missing current documents are shown as intentional empty states, not generic
  errors.
- Version history is shown per document type.
- `stageToDocumentType()` maps the current coaching stage to the matching
  document type for the default selected tab and "View current document" actions.
  `idea` and `completed` map to `null`.

## Key Design Decisions

- React + Vite + TypeScript was chosen for a small, fast frontend with good
  type safety and minimal framework ceremony.
- TanStack Query owns server state because nearly every authenticated screen is
  API-backed and benefits from query keys, retries/refetches, and cache updates.
- Zustand owns small client-only state: auth status/user and current chat session
  IDs. It is not persisted.
- Token storage is deliberately conservative for v1: access token in memory,
  refresh token in `sessionStorage`, no "remember me." This avoids persistent
  browser-restored login while still allowing normal same-tab reload recovery.
- The token ADR explicitly says no third-party script, analytics SDK, chat
  widget, or ad script may be added without revisiting the token-storage
  decision, because the current XSS risk assumption depends on first-party-only
  script execution.
- Stage movement mirrors the coaching harness: the model may judge readiness,
  but the frontend only presents a confirmation. The user must manually advance.
- The advance-stage action is hidden/not clickable when `current_stage` is
  `completed`; the frontend does not rely on catching the backend 409.
- Completed stage is a terminal UI state with a distinct completion indicator.
  Chat remains visible in a free-form/completion mode, but no advance action is
  shown.
- Set-stage only allows going back to strictly prior coaching stages. For
  `completed`, all seven coaching stages are valid go-back targets.
- Chat readiness UI is driven by `ChatResponse.stage_readiness`, not inferred
  from text or from a manual button alone.
- Document rendering is purpose-built per framework, not a generic key/value
  dump, so each generated artifact has a layout that matches its backend shape.
- No WebSocket or streaming transport was added. Poll/refetch via TanStack Query
  is enough for v1 because chat responses are synchronous.

## Known Technical Debt / TODOs

- No real chat streaming yet. AgentOps may eventually want token-level latency,
  partial response events, or tool-call progress, but the frontend currently
  only sees completed turns.
- No frontend analytics or telemetry hooks exist yet.
- API errors are mostly surfaced locally as form errors or inline messages.
  There is no global toast/error boundary pattern.
- The API client has refresh/retry behavior but no structured client-side event
  reporting for refresh failures, retry outcomes, latency, or request IDs.
- The app does not yet persist selected startup or selected document tab across
  browser restarts.
- Chat session IDs are stored only in memory/Zustand for the tab. On reload, the
  history endpoint can default to the latest session when no `session_id` is
  supplied, but the frontend does not yet expose a session picker.
- Pagination exists in the chat-history API shape but the UI currently focuses
  on the initial/latest history view. Older-message loading can be expanded.
- Document version history shows version metadata, not a side-by-side diff or
  restore workflow.
- Mobile/responsive styling is present but has not been deeply device-tested
  beyond component/layout review.
- Accessibility basics are present through semantic controls/labels, but no
  full keyboard/screen-reader audit has been done.
- There is no automated end-to-end browser test covering login to startup to
  chat to document workflows.
- The Vite dev server logs are ignored via `frontend/.gitignore`, but the local
  dev server itself may still be running from the session if not manually
  stopped.

## Codex CLI Pitfalls

- Avoid parallel shell reads in this repo on the current Windows sandbox. The
  project saw repeated `CreateProcessWithLogonW failed: 1056` issues during
  concurrent commands. Use sequential command execution unless the environment
  changes.
- Docker/testcontainers may require escalation on this machine due to Windows
  Docker Desktop named-pipe permissions. This was environmental, not caused by
  app code.
- `.tmp/pytest-of-ADMIN` permission warnings are also local/environmental so
  far. Flag them again if they affect actual test/build results.
- Do not accidentally commit generated frontend runtime artifacts:
  `frontend/dist/`, `frontend/node_modules/`, `frontend/vite-dev.out.log`, and
  `frontend/vite-dev.err.log` are ignored.
- Be careful with untracked frontend files in future phases. The frontend was
  added as a new subtree, so `git add .` is convenient but should still be
  reviewed with `git diff --cached --name-only`.
- Frontend auth state and API token state are split intentionally. If AgentOps
  adds request instrumentation, do not bypass `apiRequest()` or auth failure
  notifications.
- The frontend treats many 404 document responses as "not generated yet."
  AgentOps should distinguish expected 404s for documents from true ownership or
  routing errors when designing metrics.
- Chat history rendering depends on backend `sequence`, not `created_at`, to
  avoid ordering bugs from timestamp ties.
- `stage_readiness` is trusted as returned by the orchestrator. The backend v1
  limitation is accepted: it does not cross-check the tool call's
  `current_stage` argument against the startup's actual `current_stage`.

## Touchpoints With AgentOps

Frontend events worth instrumenting later:

- Auth bootstrap starts/succeeds/fails.
- Login/signup/logout attempts and failures.
- Refresh-on-401 starts/succeeds/fails.
- Startup list load/create/select failures.
- Stage set/advance attempts, successes, blocked attempts, and backend errors.
- Chat send start/success/failure, including startup ID, session ID presence,
  current stage, response latency, and whether `stage_readiness` was returned.
- Stage-readiness prompt shown, confirmed, dismissed, and missing-field count.
- Chat history hydration success/failure and message count.
- Document current-version load success/404/error.
- Document history load success/error and version count.
- "View current document" actions from workspace header and chat panel.

Current telemetry hooks:

- None. There is no client-side logging, analytics SDK, tracing SDK, metrics
  collector, or event bus.
- Any new telemetry must respect the token ADR: no third-party script should be
  added until the sessionStorage refresh-token decision is revisited.

Places where latency/errors surface today:

- Auth form errors display inline on login/signup.
- Boot-time auth checking shows a full-screen checking state.
- Mid-session refresh failure routes to login by setting auth status to
  unauthenticated.
- Startup mutations display inline errors in the workspace.
- Chat send errors display inline in the chat panel.
- Document current-load non-404 errors display as errors; 404 becomes an empty
  "not generated yet" state.
- Document history errors display inside the version-history panel.

Places errors may be easy to miss:

- Refresh failures intentionally clear session state quickly; without AgentOps
  instrumentation, the reason may be invisible beyond the user landing back on
  login.
- Expected document 404s are swallowed into empty states.
- Chat readiness absence is normal when the tool was not called or when malformed
  readiness data is defensively ignored.
- The non-streaming chat flow does not expose intermediate tool-call progress to
  the frontend.

Backend logging conventions to preserve:

- Tool calls are already persisted as audit data in the orchestrator flow.
- Chat messages are stored as user/assistant-visible history; raw tool messages
  should not be exposed to the frontend.
- Ownership-sensitive routes return 404 for missing/non-owned resources.

## Current Status

Frontend/UI phase is implemented, reviewed, committed, and pushed to
`origin/main`.

Commits:

- `aef096f Add frontend API support endpoints`
- `ad8b6dc Build frontend UI phase`

Review status:

- Backend mini-checkpoints approved:
  - `ChatResponse.stage_readiness`
  - chat history read endpoint
  - `GET /startups`
- Frontend checkpoints approved:
  - project scaffold/auth/token lifecycle
  - startup shell/stage controls
  - chat/history/readiness prompt
  - document views/version history

Verification run during the phase:

- Frontend typecheck passed.
- Frontend Vitest suite passed.
- Frontend production build passed.
- Backend route/service tests for the mini-checkpoints passed after local
  Docker/sandbox permission issues were resolved.

Still needed before product-complete:

- Manual end-to-end run against a live backend with real auth/startup/chat/doc
  flows.
- Browser QA on mobile and narrow layouts.
- Accessibility pass.
- AgentOps instrumentation for frontend actions, API failures, auth refresh
  failures, chat latency, stage transitions, and document generation visibility.
- Decide whether future phases continue the direct-to-`main` workflow or switch
  to feature branches and real GitHub PRs.
