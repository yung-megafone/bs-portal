# B.S. Portal Architecture Overview — v0.2.0-alpha

B.S. Portal is a Django modular monolith backed by MySQL/InnoDB.

## Authority boundaries

### MySQL/InnoDB

Authoritative for operational relational state:

- users and department membership;
- BAM assets, status, custody, requests, reservations, checkouts, events;
- SHIT tickets, asset links, comments, attachment metadata, events;
- Timeclock punches, corrections, events;
- Django sessions/admin/auth state.

### Filesystem / future object storage

Authoritative for uploaded binary bytes such as BAM evidence and SHIT attachments. MySQL stores metadata, managed file path, ownership/context, and SHA-256.

Portable `.bsbackup` archives can carry the MySQL dump and MEDIA_ROOT together.

### Git / Markdown PSOP repository

Remains the intended authority for controlled Policies, Standards, and Operating Procedures. BSP currently stores optional document identifiers/references; a full PSOP synchronization module remains future work.

## Implemented Django apps

- `core` — dashboard, public policy/about pages, browser preference utilities, portable backup/restore, packaged first-run.
- `identity` — custom UUID user.
- `departments` — departments and memberships.
- `bam` — assets and resource allocation/custody.
- `shit` — operational ticketing.
- `timeclock` — immutable punch/correction workflow.

Planned domains such as NSEC/PSOP/intake/unified audit remain future work rather than partially fictionalized current modules.

## Service-layer rule

> Views request operations. Services perform operations. The database enforces invariants where supported; services enforce higher-order workflow rules. Domain history explains what happened.

Examples:

- SHIT Board movement calls the same ticket status service used by the normal management form.
- BAM automatic allocation calls the same allocation/checkout functions used by manual management, with explicit `automated` metadata.
- Timeclock correction appends a correction instead of mutating the original punch.

## Deployment modes

### Source development

Django `runserver`, local MySQL, manually reviewed migrations.

### Staging/production web

Django under the hosting/reverse-proxy environment with HTTPS/security settings and external MySQL.

### Packaged Windows desktop

PyInstaller EXE + Waitress + WhiteNoise + private localhost MySQL service. Persistent state remains outside the executable in ProgramData.

## Current audit posture

Each operational domain writes events/history, but BSP does not yet provide the future hardened central append-only audit ledger or DB-role immutability controls. See [Audit Model](audit-model.md).
