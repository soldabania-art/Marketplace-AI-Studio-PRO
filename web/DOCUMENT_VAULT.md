# TROVENDI Document Vault

> 2026-09-12 review: code foundation, not production-certified. [T11/T12](DEVELOPER_BACKLOG.md) cover transport, scanner lifecycle and authorization gaps.

## Purpose

The vault is the tenant-scoped evidence layer for seller, buyer/order and fulfillment operations. Binary files live in a dedicated **private** object store. PostgreSQL stores identity, ownership, links, hashes, retention state and immutable access events; it never stores the file body.

## Supported records

- seller: contracts, invoices, UПД, acts, waybills and accounting exports;
- fulfillment: contracts, tariffs, acceptance/dispatch acts, loss/damage claims and returns;
- order/buyer: fiscal receipts, returns and order evidence received through an authorized marketplace or fiscal-data integration.

Raw payment-card data, passwords, API tokens, buyer-document scans and unrelated personal data are prohibited. Buyer identifiers and external order/document references must be stored as keyed or one-way references unless the business process and jurisdiction require recoverable data.

## Security lifecycle

`authorize → private upload → hash/finalize → quarantine → malware scan → available → retention/legal hold → disposition review`

- Every operation resolves the authenticated user against the selected store.
- Blob paths contain opaque UUIDs and no filenames, emails, phone numbers or order numbers.
- Files are private and served only through an authenticated download route with `Cache-Control: private, no-store`.
- SHA-256 is calculated before finalization. Replacements create a new document/version; stored evidence is never silently overwritten.
- New uploads remain unavailable while `scan_status=pending` or when malware is suspected.
- Reads, exports, retention changes, legal holds and deletions create immutable audit events.

## Retention

Retention is policy-driven by document class, seller jurisdiction, transaction country and legal hold. The application must not hard-code one universal period for RF and CIS. No automatic deletion is allowed until the applicable legal/accounting/privacy policy is approved and versioned. Legal hold blocks disposition regardless of the normal deadline.

## Next production gates

1. Provision and bind a dedicated private Blob store via `DOCUMENT_BLOB_READ_WRITE_TOKEN`.
2. Connect an asynchronous malware scanner to the implemented HMAC-signed `/scan-results` callback (`MARKETPLACE_DOCUMENT_SCAN_WEBHOOK_SECRET`).
3. Protected download is implemented with store authorization, SHA-256 integrity verification and read audit; add multi-document export approval before bulk exports.
4. Add country-specific, lawyer/accountant-approved retention policies.
5. Add connectors for OFD/fiscal receipts, marketplace order documents, EDI and fulfillment partner documents.
6. Add data-subject request workflows without deleting records under accounting or legal hold.

## Audit corrections — 2026-09-12

The lifecycle above is the target contract. At baseline f090a4b, finalize does not enqueue scanner work, callback duplicates are not idempotent, and scan error cannot be retried through the existing callback. Membership checks do not yet implement a document-role matrix or require a seller–partner agreement for partner links. These must not be described as completed controls.

Current upload/download Next.js handlers buffer file bodies up to 25 MB. This exceeds the ordinary Vercel Function request/response limit of 4.5 MB ([official limit](https://vercel.com/docs/functions/limitations), checked 2026-09-12). Implement authorized direct private upload or dedicated backend transport and a protected download transport; do not expose private documents through public marketplace asset storage.

Before enabling the module commercially, verify scanner submission/retry/replay, object identity and size/hash, actor role, related store/partner scope, immutable versions, retention and legal holds. Receipts and buyer records must come from an authorized source; their existence in the concept is not a claim that marketplaces expose all buyer documents.
