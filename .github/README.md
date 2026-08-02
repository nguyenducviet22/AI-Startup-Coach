# GitHub Actions and Render deployment prerequisites

The workflows in this directory are the sole production deployment trigger. Before enabling their deploy jobs:

1. Create or confirm the backend and frontend services in Render.
2. In each service's Render Dashboard **Settings**, copy its deploy hook URL.
3. Create a GitHub Actions environment named `production`, with no required reviewers for this phase.
4. Add the hook URLs as environment-scoped secrets named `RENDER_BACKEND_DEPLOY_HOOK_URL` and `RENDER_FRONTEND_DEPLOY_HOOK_URL`.
5. Disable Render's native auto-deploy-on-push setting for both services. GitHub Actions must remain the only deploy trigger.

Each deploy job references its hook through the environment-neutral `RENDER_DEPLOY_HOOK_URL` variable. A future staging job can use `environment: staging` and staging-scoped hook secrets without renaming the production job logic.

The backend has no configured linter or formatter. This is intentionally deferred as a code-quality decision and is not added by these workflows.
