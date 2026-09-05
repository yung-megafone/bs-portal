# Authorization — Current Alpha Behavior

B.S. Portal `v0.2.0-alpha` uses Django authentication plus application-level module rules. This document records what the code currently enforces; it is not a claim that the production RBAC design is complete.

## Identity roles

### Django flags

- `is_active` — active account.
- `is_staff` — current modules generally treat as global operational agent and allows Django Admin subject to Django permissions.
- `is_superuser` — global authority and required for in-app backup/restore.

### DepartmentMembership roles

- Member;
- Manager;
- Department administrator.

## SHIT

### View

Staff/superuser, requester, assigned user, or active member of assigned department.

### Manage

Staff/superuser, assigned user, or active member of assigned department.

Requester alone is not sufficient.

### Internal notes

Only ticket managers.

### All-ticket scope

Staff/superuser only.

## BAM asset requests

### View BAMR

- staff/superuser;
- requester;
- Manager/Department administrator in at least one requested department.

### Manage one requirement

- staff/superuser; or
- Manager/Department administrator for that requirement's department.

### Whole-request management

Non-staff user must have Manager/Admin authority over **every** department represented by request items.

### Self release

Only the active checkout's current custodian may use the self-service release endpoint.

## Timeclock

- user may clock only themselves in/out;
- staff only may append punch corrections.

## Backup/restore

In-app data-management routes are superuser-only.

## Backlink privacy

Cross-domain backlinks are permission-filtered. A user allowed to view a BAM asset does not automatically receive hidden BAMR/SHIT request identifiers. Checkout/history prose also redacts restricted BAMR IDs where necessary.

## Future RBAC direction

The final system is expected to evolve toward explicit subject/action/resource/scope permissions (for example `bam.asset.modify` or `shit.ticket.assign`) rather than relying on current broad staff/department-agent shortcuts. DepartmentMembership should remain an input to scoped authorization rather than hard-coded business identity.
