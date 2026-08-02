# Frontend agent guide

These instructions apply to files under `frontend/` and complement the root
repository guide.

## Architecture

- `src/api/` owns HTTP clients and transport-facing types.
- `src/features/` owns product workflows and feature-local components.
- `src/components/` contains reusable application UI.
- `src/stores/` contains client state; server state belongs in React Query.
- `src/test/` contains shared test setup.

## Non-negotiables

- Keep TypeScript strict and avoid `any` or unchecked type assertions.
- Reuse the API client and typed API modules instead of calling `fetch` ad hoc.
- Preserve loading, empty, error, and retry states for network-backed UI.
- Keep controls keyboard accessible with visible focus and accessible names.
- Do not duplicate server state into Zustand stores without a documented reason.
- Add or update Vitest/Testing Library tests for user-visible behavior changes.
- Prefer semantic queries and observable behavior over implementation-detail tests.

## Verification

Run `npm run lint`, `npm run typecheck`, and the narrowest relevant Vitest test
from `frontend/`. Before finishing a frontend change, run `npm test` and
`npm run build`; visually check responsive behavior when layout changes.
