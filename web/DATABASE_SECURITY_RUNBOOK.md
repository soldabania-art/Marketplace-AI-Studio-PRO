# TROVENDI database security and anti-exfiltration runbook

Status: **production launch gate**. This document protects customer data, marketplace credentials and backups against mass extraction. It does not claim that any internet service is impossible to compromise.

## Security invariant

Compromise of one browser session, application process, deployment token, database credential or backup location must not automatically grant an attacker every other layer. Every control below is independent and failures are expected to be containable.

## Already enforced in the application

- Every seller-data route resolves the requested store through the authenticated user's workspace membership. Unknown and foreign store IDs return `404`.
- Marketplace credentials are encrypted before database storage and are never returned to the browser after entry.
- Production startup fails unless PostgreSQL, transport encryption, HTTPS, a strong JWT secret and the credential-encryption key are configured.
- Sessions are individually revocable. Password reset revokes all existing sessions.
- Login attempts are limited by both account and IP fingerprints; reset and verification requests have independent limits.
- Production API documentation is disabled. API responses are marked `no-store`; central security headers prevent framing and MIME sniffing.
- Bulk administrative user access requires an explicit platform-admin identity and remains server-side.

These controls reduce attack surface. They do **not** replace network isolation, database roles, monitoring or restore testing.

## Infrastructure launch checklist

### PostgreSQL network and identity

- Disable public database ingress. Connect only from the production backend through a private network or provider-controlled secure connection.
- If private networking is temporarily unavailable, use a narrow IP allowlist and TLS certificate verification (`sslmode=verify-full`) rather than relying only on a password.
- Maintain separate credentials for migrations, runtime DML and read-only support/analytics. The runtime role must have no `SUPERUSER`, `CREATEDB`, `CREATEROLE`, `BYPASSRLS` or schema-owner privileges.
- Never use the provider's owner/admin connection string in the application runtime.
- Rotate database and application secrets on a schedule and immediately after staff departure, suspected exposure or incident containment.
- Keep secrets only in the deployment secret store. Never expose `DATABASE_URL`, JWT secrets or encryption keys through `NEXT_PUBLIC_*`, logs, analytics or AI prompts.

### Database authorization

- Continue mandatory workspace/store predicates in application queries and negative cross-tenant tests.
- Add PostgreSQL Row Level Security table by table after migration and connection-pool behavior are tested. Do not label RLS active until policies and bypass-role checks run in CI against PostgreSQL.
- Add step-up authentication and an owner-visible audit event before any future bulk export. There is no unrestricted database-dump endpoint.
- Bound list endpoints with pagination before enterprise-scale catalogs are enabled; alert on enumeration patterns and abnormal response volume.

### Encryption and backups

- Enable provider encryption at rest and encrypted point-in-time recovery.
- Store backup copies under a different restricted identity/account from the runtime application. The application role must not be able to delete backups.
- Encrypt backup exports with a managed KMS key, restrict decrypt permission, log every decrypt, and apply retention/immutability rules.
- Run a documented restore test at least quarterly into an isolated environment; verify integrity and record recovery time and recovery point.
- Marketplace tokens are field-encrypted today. Before high-risk enterprise data is stored, introduce envelope encryption with per-tenant data-encryption keys for selected sensitive fields. Keys and ciphertext must not live under the same unrestricted identity.
- Key rotation requires versioned ciphertext, dual-read migration, audit records and a tested rollback; never rotate by destructively overwriting the only decryptable copy.

## Edge and API protection

Vercel's platform DDoS protection is only the outer layer. Stage proposed WAF limits in **log** mode first, inspect legitimate traffic, then publish deliberately in the dashboard:

| Scope | Initial log-only threshold | Reason |
| --- | ---: | --- |
| `POST /api/auth/login` | 60 requests / IP / minute | Blocks obvious credential stuffing while allowing shared office networks |
| `POST /api/auth/password-reset` | 20 requests / IP / 15 minutes | Limits email/reset abuse |
| `/api/*` | 600 requests / IP / minute | Broad emergency ceiling; tune around sync traffic |

Keep stricter deterministic limits inside the backend because edge IP rules alone do not protect accounts behind proxies or distributed attackers. Never bypass the firewall for convenience during an incident.

## Monitoring and response

Alert on repeated authorization failures, access to many store IDs, unusual download volume, new admin activity, connection-string changes, backup decrypts and sudden marketplace-token failures. Logs must contain request ID, actor ID, workspace/store scope, route, result and event time, but never raw credentials or complete marketplace payloads.

If exfiltration is suspected:

1. Stop external writes and isolate affected deployments without deleting evidence.
2. Revoke active sessions and marketplace tokens in the smallest confirmed scope.
3. Rotate JWT, database and credential-encryption secrets using the tested rotation procedure.
4. Disable suspect identities, preserve immutable audit/provider logs and determine the accessed tenant/time range.
5. Restore only when integrity is proven; validate application and backup state separately.
6. Notify affected parties according to contracts and applicable law; record decisions and timestamps.
7. Add a regression test and close the root cause before re-enabling normal traffic.

## Not yet complete

- PostgreSQL RLS is planned but is not yet the active authorization boundary.
- Per-tenant envelope encryption for business-sensitive fields is planned; current full database dumps remain sensitive.
- MFA/passkeys and step-up authorization for future exports/admin actions are required before broad production onboarding.
- WAF rules require traffic observation and explicit publication in the Vercel project; code cannot truthfully claim they are active until verified.
