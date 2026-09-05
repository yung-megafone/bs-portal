# B.S. Portal — Alpha

Internal operations platform for B.S. Supply Co.

B.S. Portal is an actively developed Django modular monolith for internal business operations. The project uses MySQL/InnoDB as its primary datastore and server-rendered Django templates rather than a separate frontend application.

The portal is beyond the original foundation-only stage: identity, departments, BAM asset management, SHIT ticketing, and Timeclock workflows are implemented and usable. It remains **alpha software** while authorization, audit enforcement, backup/restore, security hardening, and additional operational modules are still being developed and reviewed.

The current application release is **v0.1.0-alpha**. Human-facing release metadata is defined in `portal/apps/core/version.py` so the UI and tests use one version source of truth.

## Documentation

- [B.S. Portal Operator Guide](docs/user-guide.md) — illustrated day-to-day use of Dashboard, Departments, BAM, SHIT, Timeclock, and the current admin/back-office view.
- [Documentation index](docs/README.md) — operator, development, architecture, ADR, privacy, and security documentation.
- [Privacy Policy](PRIVACY.md) — privacy-first design principles, data handling, retention, and self-hosting considerations.
- [Security Policy](SECURITY.md) — alpha security posture, reporting guidance, deployment baseline, and planned hardening.
- In-app information pages — `/about/`, `/privacy/`, `/security/`, and `/license/` expose the current version, credits, policies, and MIT license without requiring authentication.

## Current modules

### Identity and Departments

- custom UUID-backed user model
- Django authentication
- departments and department memberships
- application-level access controls used by operational modules

### BAM — B.S. Asset Management

- asset registration and immutable human-readable asset IDs
- asset types and lifecycle statuses
- department ownership and current custodian tracking
- custody history
- status and detail-change event history
- asset evidence / file attachments with SHA-256 metadata
- asset relationships
- SHIT ticket linkage

### SHIT — Software Helpdesk and Internet Technology

- incident, request, access, change, problem, PSOP/documentation, feedback, and general ticket types
- SEV-1 through SEV-5 severity classification
- department and user assignment
- requester-visible comments and internal notes
- file attachments with SHA-256 metadata
- BAM asset and PSOP/document references
- ticket event/history trail
- conventional searchable/filterable List view
- operational Board view using the same Ticket records and workflow services
- drag/drop status movement with server-side authorization
- independent manual queue ordering
- accessible non-drag queue controls
- responsive Dense / Compact ticket-detail layouts

Ticket identifiers use the current immutable format:

```text
SHIT-YY-HHHHHH
```

where `HHHHHH` is a six-character uppercase hexadecimal suffix protected by a database uniqueness constraint.

### Timeclock

- employee clock in / clock out
- immutable authoritative punch records
- append-only punch corrections rather than destructive edits
- derived effective punch state
- timeclock audit events

### Core platform

- authenticated dashboard
- health endpoint
- MySQL/InnoDB configuration
- environment-specific Django settings
- local media storage
- cPanel / Passenger staging entry point
- service-layer business logic
- database constraints for important invariants
- automated tests for core and operational behavior

## Baseline

- Python 3.11
- Django 5.2 LTS series
- MySQL / InnoDB
- Django templates with targeted vanilla JavaScript
- no separate frontend build pipeline
- Linux deployment target
- Windows 10-friendly local development
- cPanel / Passenger staging target

## Environments

- `config.settings.local` — developer workstation
- `config.settings.test` — automated tests
- `config.settings.staging` — `dev.bssply.co`
- `config.settings.production` — future production deployment

Secrets and machine-specific configuration belong in `.env` and must not be committed.

## Quick start — Windows

### Preferred: one-click launcher

Install Python 3.11, MySQL, and Git, then create a local MySQL database/user for the portal.

From an intact repository checkout, double-click:

```text
Launch-BS-Portal.cmd
```

The launcher will:

- locate the repository root
- create `.venv` with Python 3.11 if needed
- install dependencies when `requirements.txt` changes
- create `.env` from `.env.example` on first run
- validate required MySQL configuration
- run Django system checks
- check for pending migrations without applying them
- start the Django development server
- open the portal in the default browser

The launcher **does not automatically apply database migrations**. If migrations are pending, startup stops and reports them for review.

On the first run, edit the generated `.env` with your local MySQL credentials and launch again.

When a reviewed migration needs to be applied manually:

```powershell
.\.venv\Scripts\python.exe portal\manage.py migrate --settings=config.settings.local
```

To create the first administrative account:

```powershell
.\.venv\Scripts\python.exe portal\manage.py createsuperuser --settings=config.settings.local
```

### Manual PowerShell setup

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
# edit .env
python portal/manage.py check --settings=config.settings.local
python portal/manage.py migrate --settings=config.settings.local
python portal/manage.py createsuperuser --settings=config.settings.local
python portal/manage.py runserver --settings=config.settings.local
```

Then visit `http://127.0.0.1:8000/`.

## Quick start — Linux

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
# edit .env
python portal/manage.py check --settings=config.settings.local
python portal/manage.py migrate --settings=config.settings.local
python portal/manage.py createsuperuser --settings=config.settings.local
python portal/manage.py runserver --settings=config.settings.local
```

## Verification

```bash
python portal/manage.py check --settings=config.settings.local
python portal/manage.py test --settings=config.settings.test
```

Before committing schema changes, review generated migrations rather than treating them as an automatic startup step.

## Architecture

B.S. Portal follows a domain-oriented modular-monolith structure under `portal/apps/`.

The operating rule is:

> Views request operations. Services perform operations. The database enforces invariants where supported; services enforce higher-order workflow rules. Audit records explain what happened.

In practice:

- templates render application state rather than containing business logic
- views handle HTTP concerns and authorization boundaries
- service functions perform multi-write business operations
- database constraints protect important invariants where practical
- operational changes generate domain-specific event/history records

See `docs/` for architecture decisions and deployment documentation.

## Alpha status and remaining work

The portal is functional, but it is **not yet considered production-hardened**.

Major work still planned or incomplete includes:

- NSEC assessment/compliance workflows
- formal asset-intake workflows beyond direct BAM registration
- PSOP repository synchronization
- centralized/enforced append-only audit controls beyond existing module event histories
- production authorization matrix / RBAC hardening
- MFA / passkeys
- rate limiting
- database role separation
- external/object-storage strategy where required
- backup/export and restore tooling with tested recovery procedures
- dependency and static-analysis review
- threat modeling and broader security review
- production deployment validation

The current alpha designation should remain until these foundations are sufficiently stable for broader operational testing and the security model has been reviewed as a system rather than only module-by-module.

## Security and privacy

Treat the current codebase as alpha software. The project intentionally favors first-party, self-hosted operational data and does not require advertising, analytics, location tracking, biometrics, or device fingerprinting to operate.

At minimum:

- do not commit `.env`, passwords, API keys, database credentials, or Django secret keys;
- do not expose a `DEBUG=True` instance to the public internet;
- keep internet-reachable staging isolated and use synthetic/disposable data;
- do not assume current application authorization is the final production RBAC model;
- review migrations and verified backups before applying schema changes to valuable data;
- protect media, logs, and backups as sensitive operational data.

See [`SECURITY.md`](SECURITY.md) for the security policy and [`PRIVACY.md`](PRIVACY.md) for the privacy-first data-handling posture.

## Staging deployment

The current staging target is `dev.bssply.co` using cPanel / Passenger.

See [`docs/development/cpanel-staging.md`](docs/development/cpanel-staging.md).


## License

B.S. Portal is released under the [MIT License](LICENSE).

The MIT license is intentionally permissive: reuse, modification, redistribution, and commercial use are allowed, provided the copyright and license notice are preserved. This provides the attribution/notice requirement wanted for the project without introducing a custom software license or restricting downstream use in ways that would make the project non-open-source.

## Development rules

B.S. Portal favors maintainability and explicit behavior over cleverness.

- keep business logic out of templates
- prefer domain-oriented apps and explicit service functions
- preserve existing behavior unless a change is intentional
- use database constraints for important invariants where practical
- add tests with behavior changes
- keep secrets out of source control
- document security-sensitive behavior when the reason is not obvious
