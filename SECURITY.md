# Security Policy

B.S. Portal is currently **alpha software**. It has meaningful security controls and authenticated operational workflows, but it is not yet considered production-hardened.

This document explains the current security boundary, safe deployment expectations, vulnerability-reporting process, and planned hardening work.

The reference application exposes a concise public security page at `/security/`; this repository document remains the fuller security policy.

## Supported versions

The project does not yet maintain multiple supported release branches.

| Version | Security support |
| --- | --- |
| Current `master` / active alpha | Best effort |
| Older snapshots / forks | Not supported by the project |

Security fixes should be evaluated against the current codebase. Operators of forks are responsible for carrying relevant fixes into their own deployments.

## Reporting a vulnerability

**Do not publish a suspected vulnerability, credential, private record, or exploitable proof-of-concept in a public issue.**

Preferred reporting path:

1. Use GitHub private vulnerability reporting / a private security advisory if it is enabled for the repository.
2. If private GitHub reporting is unavailable, contact the repository owner through a non-public contact method published on the owner's GitHub profile or B.S. Supply Co. site.
3. Include the affected revision, component, impact, reproduction conditions, and the minimum detail necessary to verify the issue.

Please avoid accessing, modifying, exfiltrating, or retaining data that is not yours while investigating a suspected issue.

## Alpha restrictions

Until the hardening work below is complete:

- use synthetic/disposable data in public or internet-reachable staging environments;
- do not expose Django with `DEBUG=True` to the public internet;
- keep staging behind an additional access boundary where practical;
- never commit `.env`, passwords, API keys, database credentials, private keys, or Django secret keys;
- do not assume application-level authorization is the final production RBAC model;
- review migrations and make a verified backup before applying schema changes to valuable data;
- do not treat Django admin as a routine least-privilege operator interface.

## Current security model

### Framework primitives

BSP intentionally relies on mature Django primitives rather than custom authentication, session, password, or cryptographic schemes.

The current base configuration includes Django authentication/session middleware, CSRF protection, clickjacking protection, HTTP-only session/CSRF cookies, `X-Frame-Options: DENY`, content-type sniffing protection, and `DEBUG=False` as the base default.

These controls are a baseline, not a complete production configuration.

### Authentication and authorization

- access to operational BSP pages requires authentication;
- the project uses a custom UUID-backed Django user model;
- module-level authorization is enforced in server-side views/services rather than trusted to client-side controls;
- SHIT separates ticket visibility from ticket-management permission;
- board status/order mutations are server-authorized and validated;
- BAM asset requests separate requester access from reservation authority; requesters may submit their own needs, while reservation operations are restricted to staff/superusers or manager/admin members of the relevant owning department;
- whole-request BAM actions spanning multiple departments require authority across every involved department, while individual reservation actions remain department-scoped;
- reservation conflicts are validated server-side inside transactions rather than trusting browser availability displays;
- reservation-backed checkout, return, and direct-handoff actions are department-authorized on the server and are not inferred from client-side state;
- active physical checkouts block new allocation even after their original reservation window has expired, preventing an overdue asset from being promised to another request before it is returned or handed off;
- administrative Django access should remain limited to explicitly trusted staff.

The authorization model is still under active review. A formal production authorization matrix and adversarial permission tests remain planned work.

### Operational history

BAM, SHIT, and Timeclock maintain domain-specific event/history records. BAM asset requests record reservation/waitlist actions separately from physical custody; reserving an asset does not silently rewrite `current_custodian`. A reservation-backed checkout explicitly creates checkout history and a custody transition, while return/direct-handoff actions close or transfer that custody with corresponding events. Timeclock corrections preserve the original punch and append corrections instead of silently rewriting history.

These histories improve accountability but should **not yet be described as a tamper-proof audit ledger**. Database-level append-only enforcement and centralized audit policy remain planned hardening items.

### Database

The project is standardized on MySQL/InnoDB with strict transactional behavior enabled by the application configuration.

Production/staging deployments should use:

- a dedicated database/user for BSP;
- least privileges necessary for normal application operation;
- separate administrative credentials for schema/maintenance work where practical;
- encrypted transport to a remote database when the database is not local/private;
- tested backups stored separately from the live database.

The development launcher intentionally detects pending migrations rather than applying them automatically.

### File uploads

BAM evidence and SHIT attachments are untrusted user-controlled content. Operators should:

- store uploaded media outside executable/static-code paths;
- prevent the web server from executing uploaded content;
- enforce appropriate upload size limits at the application/proxy layer;
- avoid trusting filename extensions or client-supplied MIME types as proof of content;
- consider malware/content scanning before exposing uploads to a broader production audience;
- restrict media access to users authorized for the related record.

### Secrets

Secrets must come from environment configuration or another deployment secret mechanism, not from committed source files.

At minimum, each non-development deployment requires a unique high-entropy Django secret key and unique database credentials.

If a secret is accidentally committed, removing it from the latest commit is **not** sufficient. Rotate/revoke the secret and then clean repository history as appropriate.

## Production deployment baseline

Before BSP is treated as production-ready, a deployment should verify at least the following:

- `DEBUG=False`;
- explicit `ALLOWED_HOSTS` and trusted origins;
- HTTPS/TLS at the public boundary;
- secure session and CSRF cookies for HTTPS deployments;
- HSTS only after HTTPS behavior has been verified and rollback implications are understood;
- reverse-proxy/web-server request and upload limits;
- least-privilege filesystem ownership and database credentials;
- private protection of `.env`, media, logs, and backups;
- tested backup **and restore** procedures;
- dependency/security update process;
- production logging that avoids unnecessary secrets/personal data;
- staff/admin account review;
- authorization tests for every privileged workflow;
- a documented incident-response and credential-rotation procedure.

## Privacy-sensitive security design

BSP is intentionally privacy-first. Security controls should protect operational records without turning the portal into an employee-surveillance platform.

The current Timeclock module records authenticated punches and corrections but is intentionally not designed to collect GPS location, biometrics, device fingerprints, advertising IDs, or continuous presence telemetry.

See [`PRIVACY.md`](PRIVACY.md) for the project's privacy posture and data-minimization principles.

## Security-sensitive development principles

Contributions should follow these rules:

- prefer mature framework/library primitives over custom security mechanisms;
- enforce authorization on the server for every state-changing operation;
- treat all browser/client values as untrusted input;
- use CSRF protection for authenticated state changes;
- preserve transactional integrity for multi-write workflows;
- keep secrets and machine-specific configuration outside source control;
- avoid logging credentials, secret tokens, or unnecessary personal data;
- keep severity/priority/business metadata distinct rather than encoding authority in presentation state;
- add focused tests for permission boundaries and security-sensitive behavior;
- document assumptions when a security decision is not obvious.


## Packaged Windows desktop build

The optional Windows package is a localhost-only convenience deployment, not a new public-network security boundary. It runs the web application on `127.0.0.1:8765` and provisions a private MySQL service on `127.0.0.1:33069`; neither service is intended to listen on a LAN/WAN interface. Runtime secrets are not stored as plaintext: application credentials use Windows DPAPI LocalMachine protection, and the MySQL root recovery secret is additionally kept in an Administrator/SYSTEM-only file. LocalMachine DPAPI should still be treated as protection at rest rather than isolation from a sufficiently privileged local Windows user.

The installer takes a SQL backup before applying the versioned migration set and preserves ProgramData database/media/backups on uninstall. The packaged build should remain unsigned until a real code-signing certificate is configured; unsigned alpha binaries may trigger Windows SmartScreen/Defender reputation warnings. Code signing is strongly recommended before broader distribution.

## Planned hardening

Major security work still planned or incomplete includes:

- production authorization matrix and RBAC hardening;
- MFA/passkeys;
- login and sensitive-action rate limiting;
- database role separation;
- centralized / database-enforced append-only audit controls;
- production security-header and cookie review;
- Content Security Policy evaluation;
- dependency vulnerability scanning and static analysis;
- upload validation/scanning strategy;
- backup/restore drills;
- threat modeling;
- authorization matrix tests;
- security review of deployment/proxy configuration;
- incident-response documentation.

## No security warranty

The project is distributed under the license in [`LICENSE`](LICENSE) and is provided without warranty. Alpha status should be treated as a real operational constraint, not merely a version label.

### BAM automation controls

BAM automatic approval and custody transfer are policy-controlled and can be disabled independently by administrators. Automatic allocation still evaluates reservation conflicts, asset lifecycle state, allocation holds, per-asset automation opt-out, requested preference mode, and stock custody before acting. Explicit manager selection remains a separate manual override path. Automatic actions are recorded in BAM audit/event history with an automation marker and a configured audit actor.
