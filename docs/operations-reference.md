# Operations & Command Reference — v0.2.0-alpha

This page is a concise command/operator reference. See the linked guides for explanation and safety context.

## Source-development commands

Run from repository root on Windows.

### Launch

```powershell
.\Launch-BS-Portal.cmd
```

No browser:

```powershell
.\scripts\launch_bs_portal.ps1 -NoBrowser
```

Custom bind:

```powershell
.\scripts\launch_bs_portal.ps1 -Bind '127.0.0.1:8001'
```

### Django check

```powershell
.\.venv\Scripts\python.exe portal\manage.py check --settings=config.settings.local
```

### Migration status

```powershell
.\.venv\Scripts\python.exe portal\manage.py showmigrations --plan --settings=config.settings.local
.\.venv\Scripts\python.exe portal\manage.py migrate --check --settings=config.settings.local
```

### Apply reviewed migrations

```powershell
.\.venv\Scripts\python.exe portal\manage.py migrate --settings=config.settings.local
```

### Create superuser

```powershell
.\.venv\Scripts\python.exe portal\manage.py createsuperuser --settings=config.settings.local
```

### Seed BAM reference data

```powershell
.\.venv\Scripts\python.exe portal\manage.py seed_bam --settings=config.settings.local
```

### BAM automation pulse

```powershell
.\.venv\Scripts\python.exe portal\manage.py process_bam_automation --settings=config.settings.local
```

### Portable backup

```powershell
.\.venv\Scripts\python.exe portal\manage.py export_portal_backup --settings=config.settings.local
```

DB only:

```powershell
.\.venv\Scripts\python.exe portal\manage.py export_portal_backup --database-only --settings=config.settings.local
```

### Restore

```powershell
.\.venv\Scripts\python.exe portal\manage.py import_portal_backup .\backup.bsbackup --yes-really-restore --settings=config.settings.local
```

### Full tests

```powershell
.\.venv\Scripts\python.exe portal\manage.py test --settings=config.settings.test
```

Module tests:

```powershell
.\.venv\Scripts\python.exe portal\manage.py test apps.bam --settings=config.settings.test
.\.venv\Scripts\python.exe portal\manage.py test apps.shit --settings=config.settings.test
.\.venv\Scripts\python.exe portal\manage.py test apps.timeclock --settings=config.settings.test
```

## Packaged Windows commands

### Normal run

```powershell
BS-Portal.exe
```

No browser:

```powershell
BS-Portal.exe --no-browser
```

### Maintenance check

```powershell
BS-Portal.exe --maintenance check
```

### Database-only safety backup

```powershell
BS-Portal.exe --maintenance backup
```

### Backup and migrate

```powershell
BS-Portal.exe --maintenance backup-and-migrate
```

## Build commands

### Normal Setup EXE

```powershell
.\Build-BS-Portal-Release.cmd
```

or:

```powershell
.\packaging\windows\build_release.ps1
```

### Offline dependency bundle

```powershell
.\packaging\windows\build_release.ps1 -BundleDependencies
```

### Build application but skip Inno Setup

```powershell
.\packaging\windows\build_release.ps1 -SkipInstaller
```

## Important URLs

| URL | Purpose |
| --- | --- |
| `/` | Dashboard |
| `/bam/` | BAM assets |
| `/bam/requests/` | BAMR requests |
| `/bam/checkouts/` | Active/My checkouts |
| `/shit/` | SHIT Board/List |
| `/timeclock/` | Timeclock |
| `/data/` | Superuser Backup & restore |
| `/admin/` | Django Admin |
| `/setup/` | packaged first-run only; disabled after user exists |
| `/health/` | health probe |
| `/about/` | version/about |
| `/privacy/` | privacy policy |
| `/security/` | security policy |
| `/license/` | MIT license |

## Source runtime defaults

- Portal: `127.0.0.1:8000`
- MySQL: `127.0.0.1:3306`
- Settings: `config.settings.local`
- Media: `<repo>/data/asset_media` unless overridden
- Backups: `<repo>/data/backups` unless overridden

## Packaged runtime defaults

- Portal: `127.0.0.1:8765`
- MySQL: `127.0.0.1:33069`
- MySQL service: `BSPortalMySQL`
- Settings: `config.settings.desktop`
- Persistent data: `%ProgramData%\B.S. Supply Co\B.S. Portal`
