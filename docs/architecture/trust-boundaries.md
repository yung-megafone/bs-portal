# Trust Boundaries — v0.2.0-alpha

B.S. Portal currently supports several deployment modes with different assumptions. A deployment label is not itself a security boundary; the surrounding OS/account/network controls still matter.

## Local source development

Typical layout:

```text
browser
  → Django runserver 127.0.0.1:8000
  → MySQL 127.0.0.1:3306
  → local MEDIA_ROOT / data / backups
```

Local development is trusted for active development and may contain operationally useful test/realistic records, but it is **not production-hardened**. `DEBUG=True`, broad developer access, and local credentials mean a developer machine should not be treated as a production confidentiality/integrity boundary.

If valuable data is used locally, protect the workstation and create portable backups before schema/workflow experiments.

## Packaged Windows desktop

Typical layout:

```text
local browser
  → Waitress 127.0.0.1:8765
  → BSPortalMySQL 127.0.0.1:33069
  → ProgramData media/backups/logs/config
```

The packaged build is intentionally localhost-only. It uses machine-local DPAPI-protected secrets and a private MySQL service. It is a deployment convenience and local operational boundary, **not** an internet-facing production server profile.

Do not bind/expose the packaged Waitress/MySQL ports to the LAN or Internet without redesigning the deployment/security boundary.

## Staging

`dev.bssply.co` is internet-exposed and therefore treated as hostile even when the data is disposable.

Recommended perimeter:

```text
Internet
  → HTTPS/reverse proxy/web server
  → Django session authentication
  → application authorization
  → MySQL/InnoDB
  → media storage
```

Use synthetic/disposable data on staging unless staging has been deliberately hardened for sensitive data.

## Production

Production should be a separate deployment/database/runtime state, not merely a renamed staging instance. Production requires the security controls described in `SECURITY.md`, including reviewed HTTPS/proxy behavior, secret management, backup/restore drills, RBAC review, and additional hardening not yet complete in alpha.

## Backup boundary

A `.bsbackup` contains database contents and optionally uploaded media. It excludes machine-local secrets but can still contain sensitive operational records, ticket comments, user/account data, evidence, and attachments.

Treat `.bsbackup` as sensitive data at rest and in transit.

## Non-boundaries

- A subdomain is a routing boundary, not necessarily an OS/user isolation boundary.
- Django Admin is not a separate database trust boundary from the application.
- Module event/history records are not yet a tamper-proof ledger against database administrators.
- SHIT/BAM visibility filters prevent ordinary application disclosure but do not protect against privileged DB/host access.
