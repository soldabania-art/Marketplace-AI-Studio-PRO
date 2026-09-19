# Platform access contract (CTRL01)

Tenant membership roles (`owner`, `admin`, `analyst`, `operator`) and platform staff roles are separate authorization domains. A platform role never grants access to a tenant store endpoint.

## Endpoint capability matrix

| Endpoint group | Platform owner | Project Manager |
| --- | --- | --- |
| `GET /auth/me` platform role/capabilities | Own effective role | Own effective role |
| `GET /admin/summary` aggregate counts | Read | Read |
| `GET /admin/overview` platform aggregates (CTRL02) | Read | Read |
| `GET /admin/users`, `/admin/jobs`, `/admin/team` | Read | Denied |
| Knowledge, fulfillment and agent-learning admin endpoints | Read/write under their existing step-up rules | Denied |
| User status, workspace plan and job replay | MFA + fresh step-up | Denied |
| Grant/revoke platform staff | MFA + fresh step-up | Denied |

`/admin/summary` contains counts only. It does not contain client identities, stores, raw jobs, job errors, billing claims or financial rows. `active_subscriptions` is a status count and does not imply that those subscriptions are paid.

## One-time bootstrap and rollout

`ADMIN_EMAILS` is only input to the explicit one-time command below. Request authorization never reads that allowlist.

```bash
cd web/backend
python -m app.bootstrap_platform_owners
```

The command succeeds only when the configured set is non-empty and every address belongs to an existing active, email-verified account. It validates the entire set before writing, refuses to overwrite any active or revoked role, and writes a durable completion marker in the same transaction. A completed rerun is a no-op. Bootstrap targets may enroll MFA after the role is persisted; every platform endpoint still requires an MFA-verified current session, and owner writes also require fresh step-up.

Do not serve old and new admin APIs together. Old replicas authorize `ADMIN_EMAILS` directly and would ignore persisted revocations. The operational sequence is:

1. Enter maintenance and drain every old API replica that serves admin routes.
2. Apply the database migration.
3. Run the explicit bootstrap command and verify its transaction completed.
4. Start only the new API version.
5. Verify the owners' MFA sessions, `/auth/me` capabilities, Project Manager isolation and owner mutation step-up.
6. Reopen platform administration.

Rolling back to old application code would re-enable allowlist authorization. Preserve revoked access through an audited configuration snapshot and a forward fix; do not use a generic code rollback for this boundary.

The last-effective-owner rule uses one PostgreSQL transaction advisory lock for role revocation and user deactivation, then re-checks the acting owner's current persisted role under that lock. SQLite tests cover sequential behavior only and do not prove the PostgreSQL concurrency contract.


## CTRL02 overview and integration gates · 13 September 2026

The overview is a database read model, not a live provider health probe. It exposes aggregate account/store/job counts without customer IDs, names, raw payloads or provider errors. Saved WB credentials do not prove provider access. Missing business metrics remain unavailable. Owner detail endpoints retain their separate guards; a Project Manager does not receive those rows.

The overview depends on the CTRL01 staff migration and guards. Its local verification does not authorize mixed old/new API versions or establish production readiness. See [CTRL02 #57](https://github.com/soldabania-art/Marketplace-AI-Studio-PRO/issues/57).

Before integration:

1. Verify the exact proposed commit in PostgreSQL CI. Run `python -m app.verify_ctrl01_migration` after both the fresh and previous-to-head upgrades, before collecting the full test suite. This checks the migrated schema without ORM table creation and refuses SQLite. The check is tracked in [#58](https://github.com/soldabania-art/Marketplace-AI-Studio-PRO/issues/58).
2. Confirm all three CTRL01 two-session concurrency cases and the CTRL02 PostgreSQL aggregate test actually pass. A SQLite skip is not evidence for either contract.
3. Inspect the combined Alembic graph when integrating independent WB01 and email-delivery changes. Their branches and CTRL01 descend from revision 0028. Resolve the graph with an explicit reviewed merge migration when required, preserving published revisions; test fresh installation and each supported existing branch path. Do not treat `head-1` on one isolated branch as proof of the combined upgrade.
4. Verify owner/manager, MFA, revoked access, partial API failures, mobile/desktop, keyboard and reduced motion in a permitted browser preview of the proposed version.
5. Integrate accepted changes in dependency order: CTRL01 before CTRL02, preserving the maintenance sequence above. Recheck the final main commit, migrations and deployment separately.

As of this local review, the seeded previous-to-head check passed only on a disposable SQLite database through the real Alembic chain. It preserves two synthetic users and proves that CTRL01 does not implicitly grant a role or complete bootstrap; it is not a production-data, backup or restore test. PostgreSQL execution, remote CI, browser verification and rollout remain pending. If another migration head is merged, adapt the direct-predecessor gate to the reconciled graph before treating it as release evidence. There is no scheduled deployment implied by this document.
