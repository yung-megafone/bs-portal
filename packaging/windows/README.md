# Windows packaged release

The Windows release converts the existing Django/MySQL application into one user-facing release artifact:

`BS-Portal-v0.2.0-alpha-Setup.exe`

The target workstation does not need Python, pip, Git, a virtual environment, Django, or a preconfigured MySQL server.

## Runtime layout

The release download is a single Setup EXE. Installed/runtime state is intentionally separated from the immutable application executable:

- `%ProgramFiles%\B.S. Supply Co\B.S. Portal\BS-Portal.exe` — PyInstaller one-file application.
- `%ProgramFiles%\B.S. Supply Co\B.S. Portal\mysql\` — private MySQL runtime installed/configured by Setup.
- `%ProgramData%\B.S. Supply Co\B.S. Portal\mysql-data\` — authoritative MySQL database files.
- `%ProgramData%\B.S. Supply Co\B.S. Portal\media\` — BAM/SHIT uploaded files.
- `%ProgramData%\B.S. Supply Co\B.S. Portal\backups\` — automatic pre-migration SQL backups.
- `%ProgramData%\B.S. Supply Co\B.S. Portal\logs\` — application/MySQL logs plus timestamped installer/bootstrap transcripts.
- `%ProgramData%\B.S. Supply Co\B.S. Portal\runtime.json` — local application configuration. Application secrets are DPAPI-protected using LocalMachine scope.
- `%ProgramData%\B.S. Supply Co\B.S. Portal\mysql-root.json` — DPAPI-protected MySQL root recovery secret readable only by SYSTEM/Administrators.

The private database service is named `BSPortalMySQL`, binds only to `127.0.0.1`, and uses port `33069` so it does not collide with a developer's normal MySQL instance on `3306`.

## Installation behavior

Setup requires elevation because it installs a Windows service. It:

1. installs/repairs the Microsoft Visual C++ runtime required by MySQL;
2. downloads the pinned MySQL 8.4 LTS Windows ZIP from Oracle when the private runtime is absent;
3. initializes the private database on first install;
4. generates random MySQL and Django secrets;
5. protects application secrets with Windows DPAPI;
6. creates the `bsportal` database and `bsportal_app` database user;
7. takes a SQL backup before applying the release migration set;
8. runs Django system checks;
9. writes a setup transcript under the ProgramData logs directory;
10. installs shortcuts and launches B.S. Portal.

On the first new database, the application opens `/setup/` and allows the localhost user to create the first administrator. That route disables itself after any user account exists.

Uninstall removes the executable/private MySQL service and binaries but intentionally preserves ProgramData database/media/backups/configuration for reinstall/recovery.

## Runtime application

`BS-Portal.exe` runs Django under Waitress on `127.0.0.1:8765`; it is not `runserver`. Static assets are served by WhiteNoise. A tray controller provides Open Portal, View Logs, and Exit actions. If another BSP instance is already listening, launching the EXE simply opens the existing portal.

BAM automation receives one catch-up pulse at application startup. Ongoing automation remains driven by the application's existing event flows unless a separate scheduled pulse is configured later.

## Building on Windows

From the repository root:

```powershell
.\packaging\windows\build_release.ps1
```

The build script creates an isolated Python 3.11 build venv, installs packaging dependencies, runs `collectstatic`, builds `BS-Portal.exe` with PyInstaller, and compiles the single installer with Inno Setup 6. If Inno Setup is missing and `winget` is present, the script attempts to install it automatically.

Artifacts are written to:

```text
release\windows\BS-Portal-v0.2.0-alpha-Setup.exe
release\windows\SHA256SUMS.txt
```

For an offline installer:

```powershell
.\packaging\windows\build_release.ps1 -BundleDependencies
```

That explicitly embeds MySQL and the VC++ redistributable into Setup. Cached files under `packaging/windows/vendor/` are ignored by normal builds unless `-BundleDependencies` is supplied, preventing accidental redistribution. Review third-party redistribution obligations before publishing that variant.

## Maintenance CLI

The packaged EXE exposes installer-oriented commands:

```powershell
BS-Portal.exe --maintenance check
BS-Portal.exe --maintenance backup
BS-Portal.exe --maintenance backup-and-migrate
```

Normal users launch the EXE without arguments.

## Code signing

The current alpha build scripts do not fabricate or embed a signing certificate. An unsigned PyInstaller/Inno Setup release can receive SmartScreen/Defender reputation warnings, especially when newly published. Before wider distribution, sign both `BS-Portal.exe` and the final Setup EXE with a trusted Windows code-signing certificate and timestamp the signatures.
