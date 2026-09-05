# Windows Packaged Release Guide — v0.2.0-alpha

This guide describes the self-contained Windows distribution target. The source architecture remains Django/MySQL; packaging removes the need for the end user to manage Python, a repository checkout, or a manually configured MySQL instance.

## 1. User-facing release artifact

GitHub/release distribution target:

```text
BS-Portal-v0.2.0-alpha-Setup.exe
```

The target workstation does not need Python, pip, Django, Git, Node, or a pre-existing MySQL installation.

## 2. Installed/runtime layout

```text
%ProgramFiles%\B.S. Supply Co\B.S. Portal\
├── BS-Portal.exe
└── mysql\

%ProgramData%\B.S. Supply Co\B.S. Portal\
├── mysql-data\
├── media\
├── backups\
├── logs\
├── runtime.json
└── mysql-root.json
```

- `BS-Portal.exe` — PyInstaller one-file Python/Django application.
- private MySQL runtime — application-owned MySQL binaries.
- `mysql-data` — authoritative packaged MySQL data.
- `media` — BAM evidence + SHIT attachments.
- `backups` — `.bsbackup` archives.
- `logs` — application/MySQL/setup logs.
- runtime/root config files — DPAPI-protected local secrets/configuration.

Uninstall intentionally preserves ProgramData state for recovery/reinstallation.

## 3. Network bindings

### Portal

```text
127.0.0.1:8765
```

Served by **Waitress**, not Django `runserver`.

### Private MySQL

Service:

```text
BSPortalMySQL
```

Binding:

```text
127.0.0.1:33069
```

The nonstandard port avoids collision with a source-development MySQL on 3306.

## 4. Installation flow

Setup runs elevated because it provisions a Windows service.

It performs:

1. check/install/repair Microsoft VC++ runtime needed by MySQL;
2. acquire pinned MySQL 8.4 LTS Windows runtime when absent;
3. initialize private data directory/service;
4. generate random DB/Django secrets;
5. protect secrets with Windows DPAPI (LocalMachine scope);
6. create `bsportal` database and `bsportal_app` account;
7. create a database-only `.bsbackup` safety copy before release migrations;
8. run migration set and Django check;
9. install shortcuts/application;
10. launch BSP.

## 5. First run

When the packaged database has no users, BSP opens localhost-only `/setup/`.

Choose:

- **Create first administrator**; or
- **Restore existing B.S. Portal backup**.

The restore path is preferred when migrating an established development/source instance. After any user exists, `/setup/` disables itself and redirects to login.

## 6. Normal runtime

Launching `BS-Portal.exe`:

1. loads/decrypts runtime configuration;
2. checks/starts `BSPortalMySQL`;
3. verifies MySQL TCP readiness;
4. initializes Django desktop settings;
5. runs Django check;
6. refuses to run if migrations are pending (rerun the installer so it can safety-backup+migrate);
7. runs one BAM automation catch-up pulse;
8. starts Waitress with 8 threads;
9. opens the browser unless `--no-browser` was used;
10. starts system tray controls.

If port 8765 already contains a BSP `/health/` endpoint, launching again opens the existing instance rather than starting a duplicate.

If another application owns 8765, BSP reports a startup error rather than guessing.

## 7. System tray

- Open B.S. Portal
- Backup & restore
- View logs
- Exit

Exit stops the local Waitress server; the private MySQL Windows service is not treated as a disposable child process.

## 8. Maintenance commands

From the installed program directory/admin shell:

```powershell
BS-Portal.exe --maintenance check
BS-Portal.exe --maintenance backup
BS-Portal.exe --maintenance backup-and-migrate
```

- `check` — verifies DB service + Django system checks.
- `backup` — creates database-only `.bsbackup`.
- `backup-and-migrate` — safety backup, run migrations, run Django check.

Normal users launch without maintenance arguments.

## 9. Building the release

From repository root on Windows:

```powershell
.\Build-BS-Portal-Release.cmd
```

or:

```powershell
.\packaging\windows\build_release.ps1
```

Build script:

- creates isolated Python 3.11 build venv;
- installs build requirements;
- forces `DJANGO_SETTINGS_MODULE=config.settings.desktop` for both the build process and PyInstaller's isolated Django hook;
- runs a Django settings preflight and verifies `ROOT_URLCONF`/WSGI configuration;
- runs collectstatic;
- builds PyInstaller EXE;
- finds/installs Inno Setup 6 through winget when possible;
- compiles Setup;
- creates SHA256SUMS.

Outputs:

```text
release\windows\BS-Portal-v0.2.0-alpha-Setup.exe
release\windows\SHA256SUMS.txt
```


### Django settings package and PyInstaller

BSP intentionally keeps environment-specific settings under `config/settings/`. PyInstaller's stock Django hook derives the default module as `config.settings`; that name resolves to the package initializer, not the desktop settings module. The release build therefore explicitly uses `config.settings.desktop` during analysis.

If the build fails during `hook-django.py` with:

```text
AttributeError: 'Settings' object has no attribute 'ROOT_URLCONF'
```

use the current `build_release.ps1` and `BS-Portal.spec`. The build should first report `Desktop settings OK: config.settings.desktop`. Do not work around the issue by duplicating settings into a new `config/settings.py`; that would conflict with the existing settings package.

### Skip installer

The build script exposes `-SkipInstaller` when only the PyInstaller application build is desired during debugging.

### Offline installer

```powershell
.\packaging\windows\build_release.ps1 -BundleDependencies
```

This explicitly embeds MySQL/VC++ payloads. Normal builds ignore cached vendor files unless `-BundleDependencies` is supplied. Review Oracle/Microsoft redistribution terms before distributing a bundled-dependency installer.

## 10. Dependency philosophy

Python/Django/Waitress/WhiteNoise/etc. are bundled inside the application build. The installer handles system/runtime dependencies rather than asking the end user to install a development stack.

The package is “single downloadable installer,” not “all persistent state literally inside one immutable EXE.” Database/media/logs/backups must live in writable ProgramData.

## 11. Backup/restore and migration from dev

See [Backup & Restore](backup-restore.md). A full `.bsbackup` is the supported migration boundary between the normal source database on port 3306 and packaged `BSPortalMySQL` on 33069.

## 12. Repair and upgrades

If the packaged runtime reports the private MySQL service is missing/stopped or the database has pending migrations, rerun the **current installer as Administrator** and use the install/repair path.

A versioned installer can safely apply its known migration set because it first creates a backup. This differs deliberately from the development launcher, which stops on pending migrations and requires manual review.

## 13. Logs

Use tray → **View logs** or open:

```text
%ProgramData%\B.S. Supply Co\B.S. Portal\logs\
```

`bs-portal.log` rotates at roughly 5 MiB with five backups under desktop settings. Setup/bootstrap also writes transcripts/logs in the ProgramData logs directory.

## 14. Code signing

Current alpha scripts do not invent a signing identity. Unsigned PyInstaller/Inno Setup binaries may receive SmartScreen/Defender reputation warnings.

Before broader distribution, sign both the application and final Setup EXE with a trusted code-signing certificate and timestamp signatures.

## 15. Security boundary

The desktop build is intentionally localhost-only. It disables HTTPS-only cookie settings because transport never leaves localhost. Do not expose the packaged Waitress port directly to a LAN/Internet as though it were the production deployment.
