# B.S. Portal Documentation — v0.2.0-alpha

This directory is the maintained documentation set for **B.S. Portal (BSP)**. The documentation is organized by audience so an operator does not need to read deployment internals, while an administrator or developer can still trace how the system behaves.

> **Release scope:** These documents describe the behavior implemented in `v0.2.0-alpha`. Planned features are called out explicitly and should not be assumed to exist merely because they have been discussed or appear in older design notes.

## Start here

| Audience / task | Document |
| --- | --- |
| Day-to-day portal use | [Operator Guide](user-guide.md) |
| Asset registration, BAMR requests, queues, checkout, release, Vanguard automation | [BAM Guide](bam-guide.md) |
| Ticket creation, Board/List views, multi-asset links, comments, attachments, queue movement | [SHIT Guide](shit-guide.md) |
| Clocking in/out and punch corrections | [Timeclock Guide](timeclock-guide.md) |
| Users, departments, permissions, BAM automation policy, Django Admin | [Administration Guide](administration.md) |
| Export/import, `.bsbackup`, dev → packaged migration, recovery | [Backup & Restore Guide](backup-restore.md) |
| Install, run, repair, build, and maintain the Windows EXE release | [Windows Packaged Release Guide](windows-release.md) |
| Common failures and diagnostic steps | [Troubleshooting](troubleshooting.md) |
| Command-line operational reference | [Operations & Command Reference](operations-reference.md) |
| Local source checkout setup | [Local Development](development/local-setup.md) |
| Test database and test commands | [Testing](development/testing.md) |
| cPanel / Passenger staging | [cPanel Staging](development/cpanel-staging.md) |
| Release summary | [v0.2.0-alpha Release Notes](release-notes/v0.2.0-alpha.md) |

## Core terminology

- **BSP** — B.S. Portal.
- **BAM** — B.S. Asset Management, the authoritative asset register and resource-allocation subsystem.
- **BAMR** — BAM Asset Request, identified as `BAMR-YY-HHHHHH`.
- **SHIT** — Software Helpdesk and Internet Technology, the operational ticket/work queue, identified as `SHIT-YY-HHHHHH`.
- **Asset ID** — `BS-{DEPARTMENT}-{TYPE}-{4HEX}`.
- **Owner** — organizational ownership of an asset (`Company` or `Managed personal`).
- **Custodian** — the account currently responsible for/holding an asset. Ownership and custody are intentionally separate.
- **Vanguard** — the conventional default stock custodian. BAM first uses the administrator-configured stock custodian; if none is configured, an active account whose username is `vanguard` is used as the bootstrap fallback.
- **Reservation** — an approved claim on an asset for a requested date window.
- **Checkout** — the physical-custody record created when a reserved asset is actually issued.
- **Allocation hold** — a hard BAM hold that removes an asset from normal/automatic availability matching.
- **Ticket↔asset relationship** — a SHIT reference to a BAM asset. It is not a reservation or checkout.

## What is implemented in v0.2.0-alpha

### Platform

- Django 5.2 / Python 3.11 modular monolith.
- MySQL/InnoDB as the operational authority in development, test, staging, packaged desktop, and intended production deployments.
- UUID-backed user identity and department membership.
- server-rendered templates with targeted vanilla JavaScript.
- global toast rendering for Django messages.
- browser-local UI preferences for theme, SHIT Board/List, and SHIT Dense/Compact detail mode.
- public About, Privacy, Security, and License pages.

### BAM

- asset registration, preferred 4-hex suffixes, search, lifecycle status, custody, evidence, relationships, and append-oriented history;
- multiple asset types/statuses through reference data;
- BAMR resource requests with multiple requirements;
- `Any`, `Prefer`, and `Require exact` allocation modes;
- automatic approval/reservation/checkout when policy and availability allow;
- date-window-aware conflicts and waitlists;
- Vanguard/default stock custody;
- explicit checkout, return, direct handoff, overdue detection, self-service release, and condition-aware holds;
- automatic queue reconciliation on application/launcher pulses and relevant asset changes;
- administrator kill switches for BAM automation;
- portable backup/restore of MySQL plus optional uploaded media.

### SHIT

- operational tickets with type, severity, status, department, assignee, document reference, comments, attachments, and events;
- Board as the default presentation for a browser with no saved preference;
- List/Board toggle and Dense/Compact ticket-detail preference persistence;
- drag/drop board status movement and independent queue order;
- accessible non-drag queue movement controls;
- typed links from one ticket to multiple BAM assets;
- BAM request backlinks from SHIT tickets where the viewer is authorized to see them.

### Timeclock

- self-service clock in/out;
- immutable punch records;
- append-only staff corrections;
- effective state derived from original punch + latest correction;
- timeclock audit events.

## Explicitly not implemented yet

The following ideas are **not** part of `v0.2.0-alpha` and should not be documented or operated as though they exist:

- automatic parsing/autolinking of `BS-*` or `SHIT-*` identifiers typed inside comments;
- formal ticket-to-ticket relationships such as Blocks / Blocked by / Duplicate / Parent-child;
- machine-enforced asset capability matching such as “discrete GPU”, “AES”, “Linux”, or “USB-C”; current automatic matching is department + asset type + availability/policy;
- named asset pools/kits as a first-class model (multi-item BAMRs exist, but capability/pool matching does not);
- automatic creation of a SHIT ticket when a returned asset is damaged; a problem release places the asset on allocation hold and records the condition;
- email, SMS, websocket, or cross-browser push notifications; current notifications are request/response toast messages in the active portal session;
- a permanent background BAM scheduler. Source and packaged startup run an automation pulse; continuous timed pulses require an external scheduler/service if desired;
- centralized immutable platform-wide audit ledger. Each implemented module has domain event/history records, but a hardened unified audit subsystem remains future work;
- final production RBAC, MFA/passkeys, rate limiting, or production security certification.

## Architecture and decisions

- [Architecture Overview](architecture/overview.md)
- [Domain Model](architecture/domain-model.md)
- [Authorization](architecture/authorization.md)
- [Audit Model](architecture/audit-model.md)
- [Trust Boundaries](architecture/trust-boundaries.md)
- [BAM v0.2 Architecture](architecture/bam-v0.2.md)
- [ADR 0001 — Modular Monolith](adr/0001-modular-monolith.md)
- [ADR 0002 — MySQL/InnoDB Authority](adr/0002-mysql-authority.md)
- [ADR 0003 — Git/Markdown PSOP Authority](adr/0003-psop-git-authority.md)
- [ADR 0004 — Binary Evidence Outside MySQL](adr/0004-object-storage.md)

## Policies

The repository root contains the project policies that also render in-app:

- [`PRIVACY.md`](../PRIVACY.md)
- [`SECURITY.md`](../SECURITY.md)
- [`LICENSE`](../LICENSE)
- [`CONTRIBUTING.md`](../CONTRIBUTING.md)
