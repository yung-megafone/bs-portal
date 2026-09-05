# Local Development Setup — v0.2.0-alpha

B.S. Portal development intentionally uses **MySQL/InnoDB**, not SQLite, so schema/constraint behavior stays close to deployment.

## Prerequisites

### Windows

- Python 3.11 with `py.exe` launcher;
- Git;
- MySQL 8.x / compatible MySQL server and client utilities;
- PowerShell.

### Linux

- Python 3.11;
- virtualenv support;
- MySQL server/client development dependencies required by `mysqlclient`;
- Git.

## Windows one-click setup/launch

From repository root:

```text
Launch-BS-Portal.cmd
```

The launcher:

1. locates repo root;
2. creates `.venv` using Python 3.11 when needed;
3. hashes `requirements.txt` and only reinstalls dependencies when the hash changes;
4. copies `.env.example` to `.env` when missing and exits so you can edit credentials;
5. validates required MySQL variables;
6. runs Django `check`;
7. runs `migrate --check` but does **not** apply migrations;
8. runs one BAM automation pulse when schema checks pass;
9. starts `runserver`;
10. opens the browser unless `-NoBrowser`.

### First launch

The launcher creates `.env` and intentionally exits. Edit:

```text
MYSQL_DATABASE=bs_portal_dev
MYSQL_USER=bs_portal
MYSQL_PASSWORD=...
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
```

Also change the local Django secret from the template placeholder.

Create the DB/user in MySQL according to your local administration policy, then relaunch.

## Manual Windows setup

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
python portal/manage.py seed_bam --settings=config.settings.local
python portal/manage.py runserver --settings=config.settings.local
```

Visit `http://127.0.0.1:8000/`.

## Linux setup

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
python portal/manage.py seed_bam --settings=config.settings.local
python portal/manage.py runserver --settings=config.settings.local
```

## Environment variables

### Django

- `DJANGO_DEBUG`
- `DJANGO_SECRET_KEY`
- `DJANGO_ALLOWED_HOSTS`
- `DJANGO_CSRF_TRUSTED_ORIGINS`
- optional `BS_PORTAL_BUILD_ID`

### MySQL

- `MYSQL_DATABASE`
- `MYSQL_USER`
- `MYSQL_PASSWORD`
- `MYSQL_HOST`
- `MYSQL_PORT`

### Media / backup / tools

- `BAM_MEDIA_ROOT` — override uploaded-file path.
- `BS_PORTAL_BACKUP_DIR` — override backup archive storage.
- `MYSQL_BIN_DIR` / `BS_PORTAL_MYSQL_BIN_DIR` — MySQL client tool location for backup/restore.

### Tests

Optional `TEST_MYSQL_*` values override the normal DB connection for `config.settings.test`.

## Settings modules

- `config.settings.local` — developer workstation.
- `config.settings.test` — automated tests.
- `config.settings.staging` — internet-facing staging target.
- `config.settings.production` — production baseline.
- `config.settings.desktop` — packaged localhost Windows build.

## Migration discipline

The development launcher deliberately stops on pending migrations. Review migration files, create a backup if data matters, then apply manually:

```powershell
.\.venv\Scripts\python.exe portal\manage.py showmigrations --plan --settings=config.settings.local
.\.venv\Scripts\python.exe portal\manage.py migrate --settings=config.settings.local
```

## BAM reference seed

`seed_bam` creates standard asset types/statuses and SR69 only when absent:

```powershell
.\.venv\Scripts\python.exe portal\manage.py seed_bam --settings=config.settings.local
```

## Portable dev data

Use `.bsbackup` rather than copying raw MySQL data-directory files. See [Backup & Restore](../backup-restore.md).
