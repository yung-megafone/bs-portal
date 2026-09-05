# Domain Model — v0.2.0-alpha

The current portal is a modular monolith. Cross-domain relationships are explicit records rather than duplicated authoritative data.

```text
User
 ├── DepartmentMembership → Department
 ├── requests / is assigned → Ticket
 ├── requests → AssetRequest
 ├── custodian → Asset / AssetCheckout
 ├── employee → Punch
 └── actor → domain event/history records

Department
 ├── Asset
 ├── Ticket
 ├── AssetRequestItem
 └── DepartmentMembership

Ticket
 ├── TicketComment
 ├── TicketAttachment
 ├── TicketEvent
 ├── TicketAssetLink → Asset
 └── AssetRequest.related_ticket ← AssetRequest

Asset
 ├── AssetType
 ├── AssetStatus
 ├── AssetCustody
 ├── AssetRelationship
 ├── AssetEvidence
 ├── AssetEvent
 ├── TicketAssetLink → Ticket
 ├── preferred/allocated ← AssetRequestItem
 └── AssetCheckout

AssetRequest (BAMR)
 ├── requester → User
 ├── optional related_ticket → Ticket
 ├── AssetRequestItem[]
 └── AssetRequestEvent[]

AssetRequestItem
 ├── requested Department + AssetType
 ├── optional preferred_asset → Asset
 ├── optional allocated_asset → Asset
 └── one-to-one optional AssetCheckout

AssetCheckout
 ├── request_item
 ├── asset
 ├── custodian
 ├── issuer/returner
 └── optional handoff_to → AssetCheckout

Punch
 ├── employee / recorded_by
 ├── PunchCorrection[]
 └── TimeclockEvent[]
```

## Ticket ↔ asset relationships

`TicketAssetLink` allows multiple BAM assets per ticket. Relationship type and ticket-specific note live in SHIT; the Asset remains BAM-authoritative.

The legacy `Ticket.related_asset` FK remains temporarily during alpha compatibility. New workflows use `TicketAssetLink`.

> Ticket↔asset relationship is not allocation. Allocation is a BAMR/AssetRequestItem workflow.

## Reservation vs checkout vs custody

- `AssetRequestItem.allocated_asset` + `ALLOCATED` means reservation.
- `AssetCheckout` means physical issuance.
- `Asset.current_custodian` is current responsibility/holding.
- `AssetCustody` preserves the custody timeline.

Keeping these separate allows future reservations while another user still holds the asset today.

## BAM automation configuration

`BAMAutomationSettings` is a singleton (`pk=1`) controlling stock custodian/automation actor and auto-approval/transfer/promotion policies.

Automation does not create a second state model; it calls the same service operations with automated event metadata.

## Binary media

BAM `AssetEvidence.file` and SHIT `TicketAttachment.file` are filesystem/object-storage references. Portable backup optionally transports MEDIA_ROOT with the DB.
