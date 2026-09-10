# TROVENDI self-service onboarding

The onboarding master is a store-scoped, read-only assessment that creates the first trustworthy value without pretending that marketplace data reveals a seller's legal or operating model.

## Flow

1. Confirm that the authenticated user can access the selected store.
2. Check the enabled Wildberries connection without returning credentials or token hints.
3. Reuse Data Health Center gates for catalog, stocks and sales freshness.
4. Show bounded evidence from the latest snapshots: card count, distinct brands, content gaps, stock units and products with observed sales.
5. Require an owner/admin to confirm reseller/importer, manufacturer, distributor or mixed operation. The confirmation is persisted and audited.
6. Return at most three evidence-backed next actions. No revenue forecast, business type or marketplace fact is invented.

The profile is versioned separately from the tenant and can later be overridden per canonical product/SKU. It guides which costing and planning questions TROVENDI asks; it does not itself establish tax, legal or accounting facts.

## Security contract

- Every read and write is resolved through store membership.
- Only owner/admin roles can confirm or change the operating model.
- The browser receives aggregate counts, never raw tokens or cross-tenant data.
- A profile change creates an operational audit event.
- Marketplace writes are outside this module.
