# Audit and Domain History — v0.2.0-alpha

B.S. Portal currently has **domain event/history records**, not yet a single hardened company-wide audit ledger.

## Implemented histories

### BAM

- `AssetEvent`
- `AssetCustody`
- `AssetRequestEvent`
- `AssetCheckout`

Automatic BAM actions use the same service paths and add `automated: true` event metadata where applicable.

### SHIT

`TicketEvent` records creation, comments/notes, attachments, status/severity/department/assignee/document changes, asset relationship changes, and queue reorder events.

### Timeclock

`TimeclockEvent` records clock in/out/correction. Punch rows are immutable and corrections append separately.

## Current limitations

- domain event tables live in the same operational MySQL authority;
- the ordinary application DB role is not yet restricted to append-only access on historical event tables;
- there is no unified request ID / cross-domain audit event table;
- administrator-level database access can still alter underlying data outside application services;
- event history is not a cryptographic ledger.

## Target direction

A future platform audit model can normalize events into a central shape such as:

```text
AuditEvent
- id UUID
- timestamp
- actor
- action
- object_type
- object_id
- request/correlation id
- before JSON
- after JSON
- metadata JSON
```

Long-term hardening may restrict the application role to insert/select (not update/delete) on authoritative audit history, but that is not implemented in v0.2.0-alpha.
