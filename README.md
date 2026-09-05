# B.S. Portal — v0.2.0-alpha

Internal operations platform for B.S. Supply Co.

B.S. Portal is an actively developed Django modular monolith for internal business operations. The project uses MySQL/InnoDB as its primary datastore and server-rendered Django templates rather than a separate frontend application.

The portal is beyond the original foundation-only stage: identity, departments, BAM asset management, SHIT ticketing, and Timeclock workflows are implemented and usable. It remains **alpha software** while authorization, audit enforcement, recovery drills, security hardening, and additional operational modules are still being developed and reviewed.

The current application release is **v0.2.0-alpha**. Human-facing release metadata is defined in `portal/apps/core/version.py` so the UI and tests use one version source of truth.

## v0.2.0-alpha highlights

`v0.2.0-alpha` is the portal's relationship, resource-allocation, and operator-QoL release. It turns SHIT and BAM from mostly separate operational modules into linked workflows while preserving the boundary between ticket work, asset references, reservations, and physical custody.

### SHIT workbench and preferences

- Board is now the default SHIT view for users without a saved preference.
- List / Board and Dense / Compact display choices persist as first-party browser preferences.
- Tickets can reference multiple BAM assets at once through typed relationships such as Related, Affected, Required, Test Equipment, Replacement / Alternate, and Supporting Resource.
- Existing single-asset ticket references are preserved through a compatibility migration rather than discarded.
- Asset relationship changes have their own SHIT event history and do not silently alter ticket status, severity, assignment, reservations, or custody.
- BAM asset records expose permission-filtered SHIT backlinks, while SHIT search and board/list views understand all linked assets.

### BAM resource requests and waitlists

- Asset-use requests are now BAM-native records with human-readable `BAMR-YY-HHHHHH` identifiers and remain separate from the SHIT operational board.
- Requests can reference supporting SHIT work, requested usage windows, desired completion dates, purpose / justification, and multiple resource requirements in one bundle.
- Each requirement supports three allocation modes: **any suitable asset**, **prefer this asset with fallback**, or **require this exact asset**.
- Exact-asset and asset-class waitlists are date-window-aware, with queue positions and non-sensitive queue explanations shown to the requester.
- Equivalent-asset selection is deterministic rather than random, and explicit manager allocation remains available when automation is not appropriate.
- Queued requests are reconciled on automation pulses and after relevant manual asset-state changes so an available asset does not remain stranded behind a stale queue entry.

### Reservation, checkout, custody, and handoff

- Reservation state remains distinct from physical custody. An approved future request can be reserved without claiming that the requester already possesses the equipment.
- Active approved reservations can become reservation-backed checkouts that transfer actual BAM custody to the requester.
- Checkout history, due dates, overdue detection, explicit return processing, and direct handoff to the next approved user are implemented.
- A non-overlapping future reservation can be approved while the asset is still checked out today, enabling clean end-of-use handoffs without fake intermediate returns.
- Overdue physical checkouts continue to block future automatic allocation until the asset is returned or deliberately handed off.

### BAM automation and Vanguard stock custody

- `vanguard` can serve as the configurable default stock custodian for unissued company assets; company ownership and custody remain separate concepts.
- New or currently unassigned eligible company assets can default to the configured stock custodian without overwriting an existing custodian.
- Available requests can auto-approve, reserve, and—when the requested window is active—auto-checkout to the requester. Unavailable requests enter the waitlist instead.
- Good-condition self-service releases can automatically promote and transfer the asset to the next eligible request; if nobody is waiting, custody returns to stock.
- Problem releases can mark an asset on allocation hold so damaged, incomplete, or needs-attention equipment is not immediately reissued.
- Automatic approval, automatic checkout / transfer, automatic waitlist promotion, automatic transfer-on-release, equivalent substitution, and the automation audit actor are administrator-configurable.
- Individual assets can opt out of automatic allocation or be placed on an explicit allocation hold while remaining available for deliberate manager action when policy permits.
- `process_bam_automation` provides an idempotent catch-up pulse for due reservations and queue reconciliation; the Windows launcher runs a safe pulse after schema checks.

### Portable backup and restore

- Superusers now have an in-app **Backup & restore** workspace that exports portable `.bsbackup` archives and restores them into the configured MySQL database.
- Portable backups contain a transaction-consistent MySQL dump, BSP version/integrity metadata, and optionally the uploaded-media tree used by BAM evidence and SHIT attachments. Database credentials, Django secret keys, DPAPI material, logs, and installer configuration are intentionally excluded.
- Restore validates the archive, rejects backups created by a newer BSP version, creates a fresh pre-restore safety backup, replaces the current schema, imports the source data, and runs the migration set bundled with the receiving installation.
- If restore fails after replacement begins, BSP attempts to roll the previous database/media state back automatically from the safety backup.
- The packaged Windows first-run screen can restore a development/server `.bsbackup` directly before an initial administrator is created, which provides the intended dev → executable migration path.
- CLI equivalents are available through `export_portal_backup` and `import_portal_backup` for scripted or recovery-oriented workflows.

### Operator QoL, privacy, and auditability

- Django messages now render as global success / warning / error / informational toast notifications throughout the portal.
- BAM request, reservation, checkout, handoff, release, queue, and automated actions continue to write explicit history rather than becoming invisible background behavior.
- Restricted request information is filtered from BAM checkout/backlink views and from audit/custody prose shown to users who cannot open the underlying request.
- Manual custody override remains available as an administrative escape hatch but is visually separated from the normal reservation-backed checkout workflow.

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
- BAM-native asset-use requests kept separate from the SHIT operational board
- human-readable `BAMR-YY-HHHHHH` request identifiers
- requested usage windows, desired completion dates, justification, and optional SHIT work references
- multi-item resource requests / equipment bundles
- allocation preferences: any suitable asset, preferred-with-fallback, or exact-asset-required
- exact-asset and asset-class waitlists
- department-scoped reservation approval and deterministic equivalent-asset selection
- reservation-backed checkout that converts approved use into physical custody
- return processing, direct handoff to the next approved user, and checkout history
- overdue checkout detection using the approved request window
- automatic approval of available BAM requests, with unavailable requests entering the waitlist
- Vanguard/default stock custody for unissued company assets, configurable from BAM automation settings
- automatic custody transfer for active approved requests, with administrator kill switches for auto-approval and auto-transfer
- automatic promotion and reconciliation of compatible waitlisted requests when an asset is released, returned, or otherwise becomes eligible
- self-service asset release by the current custodian, with condition reporting and allocation holds for damaged/problem assets
- per-asset automatic-allocation opt-out and manual allocation override
- reservation history/backlinks without silently changing BAM custody until checkout actually occurs

### SHIT — Software Helpdesk and Internet Technology

- incident, request, access, change, problem, PSOP/documentation, feedback, and general ticket types
- SEV-1 through SEV-5 severity classification
- department and user assignment
- requester-visible comments and internal notes
- file attachments with SHA-256 metadata
- typed multi-asset BAM relationships and PSOP/document references
- ticket event/history trail
- conventional searchable/filterable List view
- operational Board view using the same Ticket records and workflow services; Board is the default when no saved preference exists
- drag/drop status movement with server-side authorization
- independent manual queue ordering
- accessible non-drag queue controls
- responsive Dense / Compact ticket-detail layouts
- asset-link history for add/remove/relationship changes
- browser-local persistence for SHIT List/Board and detail-density preferences

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
- global toast notifications for Django success/warning/error messages
- superuser-only portable backup/restore with optional media transport and pre-restore safety copies
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
- packaged Windows desktop/installer target
- cPanel / Passenger staging target

## Environments

- `config.settings.local` — developer workstation
- `config.settings.test` — automated tests
- `config.settings.staging` — `dev.bssply.co`
- `config.settings.production` — future production deployment
- `config.settings.desktop` — packaged localhost-only Windows application

For source-based deployments, secrets and machine-specific configuration belong in `.env` and must not be committed. The packaged Windows build instead generates protected machine-local runtime configuration under ProgramData.


## Packaged Windows application

`v0.2.0-alpha` can also be built as a normal Windows application instead of requiring a source checkout, Python environment, or manually configured MySQL instance. The user-facing release artifact is a single file:

```text
BS-Portal-v0.2.0-alpha-Setup.exe
```

Setup installs `BS-Portal.exe`, provisions an isolated localhost-only MySQL 8.4 LTS service named `BSPortalMySQL`, generates application credentials, protects local secrets with Windows DPAPI, takes a portable database-only safety backup before release migrations, and launches the portal on `http://127.0.0.1:8765/`. Python, Django, pip, Git, and a developer virtual environment are not required on the target workstation.

The private packaged database listens on `127.0.0.1:33069` so it does not collide with a developer MySQL instance on the conventional `3306` port. Runtime data is kept outside the executable under `%ProgramData%\B.S. Supply Co\B.S. Portal`, including the authoritative MySQL data directory, uploads, application/setup logs, backups, and protected runtime configuration. Uninstall intentionally preserves that ProgramData state for recovery/reinstallation. The first-run screen can import a portable `.bsbackup` directly, making a source-development database plus uploaded evidence/attachments portable into the executable build without recreating records manually.

On a new database, the packaged app opens a localhost-only first-run page to create the initial administrator; the bootstrap route disables itself after the first account exists. The executable uses Waitress rather than Django's development server, WhiteNoise for static assets, and a small system-tray controller for opening the portal, viewing logs, or exiting the local server.

Build it on Windows with:

```powershell
.\packaging\windows\build_release.ps1
```

The finished installer and checksum file are written under `release\windows\`. By default, Setup downloads pinned runtime dependencies directly from Oracle/Microsoft when needed; an optional offline dependency bundle can be produced with `-BundleDependencies` after reviewing third-party redistribution obligations. Dependency payloads are only embedded when that switch is explicitly used, even if cached vendor files remain from an earlier build. See [`packaging/windows/README.md`](packaging/windows/README.md) for the full build/runtime design.

## Backup, restore, and dev → packaged migration

Superusers can open **Account → Administration → Backup & restore**. For a portable copy, keep **Include uploaded files** enabled and create a `.bsbackup`. The archive can be moved to another BSP installation without carrying database passwords or machine-local secrets.

For the specific dev → packaged test:

1. In the development portal, export a `.bsbackup` with uploaded files enabled.
2. Install `BS-Portal-v0.2.0-alpha-Setup.exe` on the target Windows machine.
3. On the packaged first-run screen, choose **Restore portable backup** instead of creating a temporary administrator.
4. Select the dev `.bsbackup`, type `RESTORE`, and restore it.
5. BSP creates a safety backup of the fresh packaged database, imports the dev database/media, applies any receiving-version migrations, and then returns to login using the identities contained in the restored database.

Equivalent source/maintenance commands are:

```powershell
.\.venv\Scripts\python.exe portal\manage.py export_portal_backup --settings=config.settings.local
.\.venv\Scripts\python.exe portal\manage.py import_portal_backup .\path\to\backup.bsbackup --yes-really-restore --settings=config.settings.local
```

Use `--database-only` on export only when filesystem uploads are deliberately out of scope. A database-only restore leaves the receiving installation's existing media directory untouched, which can produce dangling file references if the source database refers to files that were not transported.


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
- run one safe BAM automation catch-up pulse after schema checks pass
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
- repeated backup/restore drills and documented disaster-recovery procedures
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
