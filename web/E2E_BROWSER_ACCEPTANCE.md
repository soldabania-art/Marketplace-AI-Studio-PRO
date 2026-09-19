# Reproducible browser acceptance stand

This infrastructure-only branch combines the accepted source heads solely for CI browser verification:

- D02/#59: `017a766de74076544b905369705f563cb2feb6b2`;
- D03/#60: `1ab343dc889d0882236679ca941e1512194d20fd`;
- backend/#61: `25da973885a3d1bdf19f2626cc84a17c6bfd2a35`.

The `browser-e2e` Actions job starts an isolated local FastAPI backend, Next.js frontend, PostgreSQL and Redis. Its deterministic fixtures create platform owner and project manager, a workspace analyst, and two stores. Platform roles are intentionally distinct from workspace roles.

The D02 flow and account/admin authorization use the running backend and normal login/MFA/step-up routes. D03 source-state rendering is intercepted in Playwright only to make missing/stale/incomplete/error states and STOP reproducible; it is not server authorization evidence. No real WB, AI, email or payment call is made. Playwright JSON/HTML reports, screenshots, traces and video-on-failure are uploaded as CI artifacts.

The stand does not merge #50, does not deploy Vercel and does not declare the source PRs integrated. The exact acceptance conclusion depends on the CI run for this branch head.
