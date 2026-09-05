# BAM v0.2 Architecture

BAM v0.2 expands the original authoritative asset register into a resource-allocation and custody system while retaining MySQL/InnoDB as the operational authority.

## Authority

- MySQL: asset identity, status, custody metadata/history, requests, reservations, checkouts, events.
- filesystem/object storage: evidence bytes.
- `.bsbackup`: transport/archive container, not a live peer database.

## Identifier allocation

Asset ID remains:

```text
BS-{DEPARTMENT}-{TYPE}-{4HEX}
```

A preferred suffix is attempted first; uniqueness is arbitrated by MySQL constraints and duplicate-key retry.

BAM requests use:

```text
BAMR-YY-HHHHHH
```

## Request model

`AssetRequest` holds shared request/window/project metadata. `AssetRequestItem` holds one resource requirement so a request can represent a bundle.

Preference modes:

- ANY;
- PREFER;
- REQUIRE.

Allocation matching is currently department+type based plus availability/policy. Capability tags/pools are deferred.

## Allocation boundary

Reservation (`AssetRequestItem.ALLOCATED`) and physical checkout (`AssetCheckout`) are separate. This supports future reservations and accurate custody.

## Stock custody

`BAMAutomationSettings.default_custodian` represents inventory/stock responsibility. If unset, an active username `vanguard` is used as bootstrap fallback.

## Automation

Automation policy controls:

- auto approval;
- equivalent substitution;
- transfer on approval;
- waitlist promotion;
- transfer on release.

Automated operations call the same transactional services as manual actions and record automated event metadata.

## Release safety

Self-service release records condition. Any non-GOOD condition creates an allocation hold, returning custody to stock but preventing immediate reissue.

## Queue reconciliation

Waitlisted requirements are reconsidered on automation pulses and state-changing workflows. An overdue active checkout is treated as blocking even when its original date window has elapsed.

## Portability

Portable `.bsbackup` packages the MySQL dump plus optional MEDIA_ROOT. Packaged Windows uses this as the supported source→desktop migration boundary.

## Deferred

- capability tags and eligibility expressions;
- named pools/kits;
- automatic maintenance SHIT ticket creation;
- continuous background scheduler;
- finalized production RBAC;
- central hardened audit ledger.
