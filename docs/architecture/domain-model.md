# Domain Model — Alpha

The current portal is a modular monolith. Cross-domain relationships are explicit records rather than duplicated data.

```text
User
 ├── DepartmentMembership → Department
 ├── requests / is assigned → Ticket
 ├── custodian → Asset
 └── actor → domain event/history records

Department
 ├── Asset
 ├── Ticket
 └── DepartmentMembership

Ticket
 ├── TicketComment
 ├── TicketAttachment
 ├── TicketEvent
 └── TicketAssetLink → Asset

Asset
 ├── AssetType
 ├── AssetStatus
 ├── AssetCustody
 ├── AssetRelationship
 ├── AssetEvidence
 ├── AssetEvent
 └── TicketAssetLink → Ticket
```

## Ticket ↔ asset relationships

A SHIT ticket can reference multiple BAM assets through `TicketAssetLink`.

Each link carries an operational relationship type such as **Affected asset**, **Required for work**, **Test equipment**, **Replacement / alternate**, or **Supporting resource**. BAM remains authoritative for the asset itself; SHIT stores only the relationship and optional ticket-specific context.

The legacy single `Ticket.related_asset` foreign key remains temporarily during the alpha migration path. Migration `0004_ticket_asset_links` copies every existing legacy relationship into `TicketAssetLink`. New application workflows use the through-model rather than writing new legacy FK values.

> A ticket↔asset relationship is not a reservation, checkout, or custody transfer. Allocation is a separate BAM workflow and must not be inferred from a SHIT reference.

## Future direction

Planned domains can extend this model without changing the core ownership boundaries:

```text
AssetIntake
 ├── Attachment
 ├── ComplianceAssessment
 └── creates → Asset

PSOPDocument
 └── references authoritative Git repository object

AssetRequest / Allocation
 ├── requests one or more → Asset / AssetPool
 ├── may reference → Ticket
 └── drives reservation / checkout workflows without becoming a SHIT ticket
```
