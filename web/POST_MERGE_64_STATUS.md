# PR #64 — integrated state and next read-only WB pilot gate

Date: 19 September 2026. Authoritative integrated commit: `c7afbf3fdfb2174fe25fe86484a2f853f4e3a32a` ([merge PR #64](https://github.com/soldabania-art/Marketplace-AI-Studio-PRO/pull/64)).

## Integrated state

PR #64 integrated D02/#59, D03/#60, backend #61 (WB01/WB02, T09A/T09B, T10A, CTRL01/CTRL02 and migration follow-up #58), browser E2E stand #62, and WB pilot #63.

The exact `main` commit passed [push CI #35447787669](https://github.com/soldabania-art/Marketplace-AI-Studio-PRO/actions/runs/35447787669); Vercel status is success. These facts confirm the checks and frontend deployment status for this SHA. They do not establish production backend readiness, a deployed API/worker/database runtime, or a real Wildberries operation.

## Infrastructure facts from the repository

- The frontend requires an externally reachable `MARKETPLACE_API_URL`.
- The backend deployment contract requires separate API (`uvicorn app.main:app`) and worker (`python -m app.worker`) processes using the same image and environment.
- API and worker require shared managed PostgreSQL with TLS and a shared Redis limiter in production.
- Production configuration is fail-closed without PostgreSQL/TLS, HTTPS frontend origin, JWT, separate marketplace and MFA Fernet keys, Redis limiter and Redis URL.
- The repository contains this contract, but no evidence of provisioned API, worker, managed PostgreSQL or Redis resources, their URLs, or access to them. A Vercel success therefore does not verify those services.

## Minimal next step: isolated read-only WB pilot

Once hosting and access exist, create a non-production isolated environment with API and worker, disposable PostgreSQL and Redis, and assign its public HTTPS API URL to frontend `MARKETPLACE_API_URL`. Use a permitted test connection to run only the WB source-capability preflight and verify that import jobs are created only for sources marked `available`.

The concrete blocker is confirmed hosting/access for the separate API and worker, managed PostgreSQL and Redis, including the ability to assign the external API URL to the frontend. Until then the pilot is **BLOCKED_EXTERNAL**. Do not run production migrations or bootstrap, real WB token/import activity, email, AI, payments, or manual Vercel actions.