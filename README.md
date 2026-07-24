# B.S. Portal — Alpha

Internal B.S. Supply Co. operations platform.

This repository is the **alpha foundation** for the B.S. Portal modular monolith. This revision standardizes the project on MySQL/InnoDB to match the GoDaddy cPanel deployment environment. It intentionally starts small: identity, departments, authentication, health checks, architecture documentation, and environment separation. Operational modules such as BAM, SHIT, NSEC, intake, audit enforcement, and PSOP synchronization are staged for later milestones.

## Baseline

- Python 3.11
- Django 5.2 LTS series
- MySQL/InnoDB
- Django templates (no separate frontend build)
- Linux deployment target
- Windows 10 friendly local development
- cPanel / Passenger staging target

## Environments

- `config.settings.local` — developer workstation
- `config.settings.test` — automated tests
- `config.settings.staging` — `dev.bssply.co`
- `config.settings.production` — future `portal.bssply.co`

## Quick start — Windows PowerShell

1. Install Python 3.11, MySQL/InnoDB, and Git.
2. Create a MySQL/InnoDB database and user for local development.
3. From the repository root:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

4. Edit `.env` with your local MySQL/InnoDB credentials.
5. Run:

```powershell
python portal/manage.py migrate
python portal/manage.py createsuperuser
python portal/manage.py runserver
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
python portal/manage.py migrate
python portal/manage.py createsuperuser
python portal/manage.py runserver
```

## Verification

```bash
python portal/manage.py check
python portal/manage.py test --settings=config.settings.test
```

## Staging deployment

See [`docs/development/cpanel-staging.md`](docs/development/cpanel-staging.md).

## Current alpha scope

Implemented:

- custom UUID-backed user model
- departments
- department memberships
- Django authentication
- base dashboard
- health endpoint
- MySQL/InnoDB configuration
- local/staging/production settings separation
- cPanel Passenger entry point
- foundational tests
- architecture decision records

Not yet implemented:

- BAM Asset Management
- SHIT Ticketing
- asset intake workflows
- NSEC assessments
- append-oriented audit system
- PSOP repository synchronization
- file/object storage integration
- production RBAC policy engine
- MFA/passkeys

Those are deliberately deferred so the platform foundation can be tested first.

## Architectural rule

> Views request operations. Services perform operations. The database enforces invariants where supported; services enforce higher-order workflow rules. Audit records explain what happened.

## Security status

**Alpha software. Do not place real operational data in staging.** `dev.bssply.co` should use synthetic/disposable data until hardening and security review are complete.
