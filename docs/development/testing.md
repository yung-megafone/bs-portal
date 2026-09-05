# Testing — v0.2.0-alpha

B.S. Portal tests use MySQL/InnoDB to keep behavior representative of deployment.

## Full suite

Windows:

```powershell
.\.venv\Scripts\python.exe portal\manage.py test --settings=config.settings.test
```

Linux:

```bash
python portal/manage.py test --settings=config.settings.test
```

## Module suites

```powershell
.\.venv\Scripts\python.exe portal\manage.py test apps.bam --settings=config.settings.test
.\.venv\Scripts\python.exe portal\manage.py test apps.shit --settings=config.settings.test
.\.venv\Scripts\python.exe portal\manage.py test apps.timeclock --settings=config.settings.test
.\.venv\Scripts\python.exe portal\manage.py test apps.core --settings=config.settings.test
```

## Test database configuration

`config.settings.test` reads:

- `TEST_MYSQL_DATABASE`
- `TEST_MYSQL_USER`
- `TEST_MYSQL_PASSWORD`
- `TEST_MYSQL_HOST`
- `TEST_MYSQL_PORT`

If omitted, the normal `MYSQL_*` settings are reused. Django creates/destroys its normal prefixed test database, so the configured account needs suitable test-database privileges.

`CONN_MAX_AGE` is disabled for test settings and password hashing uses MD5 only to speed tests; these are test-only choices.

## Current important behavioral coverage

### BAM

Tests cover request creation, preference modes, reservation conflicts, waitlists, manager/requester permissions, checkout/return/direct handoff, overdue blocking, privacy filtering, Vanguard/default custody, automatic request handling, queue promotion, self-release condition holds, and automation reconciliation.

### SHIT

Tests cover service behavior, board rendering/movement, audited status/queue changes, manager/requester authorization, multiple asset relationships, relationship auditing, migration-compatibility behavior, and asset-backed search/backlinks.

### Timeclock

Tests cover clock state, duplicate-state rejection, immutable punches, corrections, permissions, and views.

### Core

Tests cover public/about pages, desktop first-run setup, backup/archive validation, backup/restore permissions, and portable restore behavior.

## Before a release

Recommended gate:

```powershell
.\.venv\Scripts\python.exe portal\manage.py check --settings=config.settings.local
.\.venv\Scripts\python.exe portal\manage.py migrate --check --settings=config.settings.local
.\.venv\Scripts\python.exe portal\manage.py test --settings=config.settings.test
```

Then build the Windows release and perform a real **dev `.bsbackup` → fresh packaged restore** test.

## When a test catches a real bug

Do not weaken the assertion merely to get green output. The Chunk 4/5 direct-handoff and BAM privacy tests are examples where local MySQL execution exposed genuine workflow defects that were fixed in services/views instead.
