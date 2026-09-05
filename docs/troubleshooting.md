# Troubleshooting — B.S. Portal v0.2.0-alpha

Use this guide before manually editing MySQL. Most failures in the current alpha are either migration mismatch, environment configuration, or an intentionally blocked workflow state.

## 1. `Table '...shit_ticketassetlink' doesn't exist`

Typical error:

```text
ProgrammingError (1146): Table 'bsportal_dev.shit_ticketassetlink' doesn't exist
```

Cause: code from the multi-asset SHIT release is running before migration `shit.0004_ticket_asset_links` was applied.

Check:

```powershell
.\.venv\Scripts\python.exe portal\manage.py showmigrations shit --settings=config.settings.local
```

Apply reviewed migrations:

```powershell
.\.venv\Scripts\python.exe portal\manage.py migrate --settings=config.settings.local
```

Do **not** manually create the table. The migration also performs compatibility backfill from the legacy single-asset field.

## 2. Launcher refuses to start because migrations are pending

This is expected development behavior. The launcher uses `migrate --check` and stops rather than silently modifying your DB.

Inspect:

```powershell
.\.venv\Scripts\python.exe portal\manage.py showmigrations --plan --settings=config.settings.local
```

After review:

```powershell
.\.venv\Scripts\python.exe portal\manage.py migrate --settings=config.settings.local
```

Relaunch.

## 3. BAMR is Queue #1 even though the asset appears free

Run an explicit pulse:

```powershell
.\.venv\Scripts\python.exe portal\manage.py process_bam_automation --settings=config.settings.local
```

Then check the BAMR's queue explanation and the asset:

1. requested date window has not already ended;
2. asset department/type match the request;
3. asset status is allocatable (not Repair/Lost/Retired/Disposed/admin Reserved);
4. Allocation hold is off;
5. Allow automatic allocation is on (for automated allocation);
6. asset is in stock custody (normally Vanguard) for automated allocation;
7. no conflicting reservation exists;
8. no active/overdue checkout blocks it;
9. exact-required request targets this exact asset;
10. global BAM auto-approval/waitlist settings are enabled.

A manager can use explicit manual allocation when automation is intentionally disabled or a future non-overlapping reservation needs to be approved while today's user still has the asset.

## 4. “Preferred asset is currently in non-stock custody”

Automatic allocation requires the asset to be unassigned or in configured stock custody. If the asset is truly on the shelf but its database custodian is still a user, use a proper return/self-release or an administrative custody correction to Vanguard. The reconciliation hook then reevaluates the queue.

Do not merely clear the custodian to trick automation if a real active checkout still exists.

## 5. Asset released but next user did not receive it

Check:

- release condition was **Good**;
- asset was not already on allocation hold;
- `auto_promote_waitlist` enabled;
- `auto_transfer_on_release` enabled;
- target reservation is active today for immediate checkout;
- target item is compatible and valid;
- no competing/conflicting reservation blocks it.

A future reservation can be promoted to Reserved without being physically checked out early.

## 6. Direct handoff fails

Target must:

- already be `Reserved` (`ALLOCATED`), not merely Waitlisted/Pending;
- be reserved for the same asset;
- not already have checkout history;
- have a request window active today or beginning by tomorrow under the direct-handoff rule.

Manual manager allocation can approve a non-overlapping future reservation even while the current checkout is active.

## 7. Problem release placed asset on hold

This is expected. Minor issue, Damaged, Missing accessory, and Needs attention all create/retain an allocation hold. Edit the asset after follow-up and clear **Allocation hold** when safe.

The current release does not automatically create a SHIT repair ticket.

## 8. Backup says `mysqldump` or `mysql` not found

Install a compatible MySQL client or tell BSP where the client `bin` directory lives:

```powershell
$env:MYSQL_BIN_DIR = 'C:\Program Files\MySQL\MySQL Server 8.4\bin'
```

Packaged BSP sets the private MySQL bin path automatically.

## 9. Restore refuses a `.bsbackup`

Common reasons:

- wrong extension/format;
- unsafe/corrupt ZIP;
- archive contains a newer BSP version than the receiver;
- SQL SHA-256 does not match manifest;
- manifest media count/size does not match archive;
- SQL contains blocked server-level statements;
- archive exceeds safety limits.

Do not bypass the validation. Fix the source/export or upgrade the receiving BSP version.

## 10. Restore succeeded but attachments/evidence are missing

Likely restored a database-only backup. The database rows may reference media paths that were not transported.

Use a new export with **Include uploaded files** enabled and restore that full archive, or deliberately copy/reconcile MEDIA_ROOT as part of a documented recovery procedure.

## 11. Restore logs me out

Expected. Import may replace `identity_user` and Django session rows. The completion page is intentionally standalone. Log in using an account from the restored database.

## 12. Packaged app says `BSPortalMySQL` is not installed / cannot start

Rerun the current Setup EXE as Administrator and use install/repair. The application checks `sc.exe query BSPortalMySQL` and attempts to start the service, but it does not recreate a missing service by itself.

Logs:

```text
%ProgramData%\B.S. Supply Co\B.S. Portal\logs\
```

## 13. Port 8765 is already in use

If `/health/` on that port identifies BSP, a second launch simply opens the existing instance. If a different process owns 8765, BSP refuses startup.

Stop/reconfigure the conflicting application or change the desktop port in runtime configuration through a controlled repair/config procedure.

## 14. Source launcher creates `.env` then exits

Expected first-run behavior. Edit `.env`, replacing `MYSQL_PASSWORD=CHANGE_ME` and validating DB name/user/host/port. Run the launcher again.

## 15. Tests cannot create the MySQL test database

`config.settings.test` uses `TEST_MYSQL_*` when set, otherwise normal `MYSQL_*` credentials. The MySQL account must have enough privileges for Django to create/drop its prefixed test DB.

Set isolated test credentials if needed:

```text
TEST_MYSQL_DATABASE=bs_portal_test
TEST_MYSQL_USER=...
TEST_MYSQL_PASSWORD=...
TEST_MYSQL_HOST=127.0.0.1
TEST_MYSQL_PORT=3306
```

Then:

```powershell
.\.venv\Scripts\python.exe portal\manage.py test --settings=config.settings.test
```

## 16. SHIT Board opens List or Dense/Compact changed unexpectedly

Preferences are browser-local. Board is default only when there is no saved view preference. Clear the BSP preference keys/cookies or use the visible List/Board/Dense/Compact controls to overwrite the saved value.

## 17. Toasts do not appear for another user's action

Current toasts are Django message responses to the browser performing/requesting an operation. They are not realtime push notifications. Another already-open browser tab/session will not receive a remote event toast until a future realtime/persistent notification subsystem exists.

## 18. Asset/ticket IDs typed in a comment do not become links

Expected in v0.2.0-alpha. Comment reference parsing/autocomplete is planned, not implemented. Use explicit BAM asset links/BAMR related ticket fields.

## 19. Checking system health

Source:

```powershell
.\.venv\Scripts\python.exe portal\manage.py check --settings=config.settings.local
```

Packaged:

```powershell
BS-Portal.exe --maintenance check
```

HTTP health endpoint:

```text
/health/
```

Expected JSON:

```json
{"status":"ok"}
```
## 20. PyInstaller fails with `ROOT_URLCONF` missing

A build log ending in:

```text
AttributeError: 'Settings' object has no attribute 'ROOT_URLCONF'
```

means PyInstaller's Django hook analyzed the package `config.settings` instead of BSP's actual desktop profile `config.settings.desktop`. This is a build-time settings-selection problem, not a missing URL configuration in BSP; `ROOT_URLCONF = "config.urls"` already lives in the shared base settings.

Current packaging fixes it in two places:

1. `build_release.ps1` explicitly sets `DJANGO_SETTINGS_MODULE=config.settings.desktop` before PyInstaller starts and runs a Django settings preflight.
2. `BS-Portal.spec` sets the same module before `Analysis`, so PyInstaller's isolated Django hook inherits it.

Re-run:

```powershell
.\Build-BS-Portal-Release.cmd
```

A healthy run should print:

```text
[B.S. Portal Build] Validating desktop Django settings for PyInstaller...
Desktop settings OK: config.settings.desktop
```

If that preflight fails, stop there and fix the settings/environment issue; do not create a second `config/settings.py`, because BSP already uses `config/settings/` as a package for local, staging, production, test, and desktop profiles.

