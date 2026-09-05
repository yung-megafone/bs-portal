# Backup & Restore Guide — `.bsbackup`

B.S. Portal `v0.2.0-alpha` uses a portable archive format so the operational database and uploaded evidence/attachments can be moved together between source-development, packaged Windows, and compatible future BSP installations.

## 1. What a `.bsbackup` contains

Normal portable export:

```text
bs-portal-YYYYMMDD-HHMMSS.bsbackup
├── manifest.json
├── database.sql
└── media/
```

`media/` is included by default and contains BSP's configured `MEDIA_ROOT`, including BAM evidence and SHIT attachments.

### Manifest

The manifest records:

- backup format (`bs-portal-backup`);
- format version;
- BSP version;
- UTC creation time;
- database engine (`mysql`);
- source database name;
- SHA-256 of `database.sql`;
- whether media is included;
- media file count/byte count.

### Deliberately excluded

Portable backups do **not** export:

- database passwords;
- Django secret key;
- Windows DPAPI blobs;
- MySQL root recovery material;
- runtime.json;
- logs;
- installer configuration.

The receiving installation uses its own local credentials/secrets.

## 2. In-app export

Requires **superuser**.

1. Open **Account → Administration → Backup & restore**.
2. Leave **Include uploaded files** checked for a portable/full application backup.
3. Create/download the archive.
4. Store the `.bsbackup` securely and, for important backups, record an external SHA-256 of the archive itself.

A DB-only export is useful for installer migration safety or deliberate schema/data-only workflows, but it does not transport evidence/attachments.

## 3. Source CLI export

Portable/full:

```powershell
.\.venv\Scripts\python.exe portal\manage.py export_portal_backup --settings=config.settings.local
```

Database only:

```powershell
.\.venv\Scripts\python.exe portal\manage.py export_portal_backup --database-only --settings=config.settings.local
```

BSP uses `mysqldump` with a single-transaction dump, triggers, utf8mb4, hex blobs, no table locks, and no server-level CREATE DATABASE/GRANT output.

## 4. MySQL client discovery

Backup/restore needs `mysqldump` and `mysql` client executables.

BSP searches:

1. normal `PATH`;
2. `MYSQL_BIN_DIR` or `BS_PORTAL_MYSQL_BIN_DIR`;
3. common Windows MySQL Server `bin` directories.

The packaged runtime sets its private MySQL `bin` directory automatically.

If source backup reports that `mysqldump.exe`/`mysql.exe` cannot be found, set for the current shell or `.env`/environment as appropriate:

```powershell
$env:MYSQL_BIN_DIR = 'C:\Program Files\MySQL\MySQL Server 8.4\bin'
```

## 5. Restore validation

Before destructive work, BSP validates the incoming archive:

- valid ZIP structure;
- safe relative paths only (no traversal/absolute/Windows-drive paths);
- no symlink archive entries;
- archive/member size limits;
- correct BSP backup format and format version;
- MySQL backend;
- source BSP version is not newer than the running receiver;
- `database.sql` SHA-256 matches the manifest;
- SQL does not begin with prohibited server-level administrative statements such as CREATE/DROP DATABASE, CREATE/ALTER USER, GRANT/REVOKE, or plugin installation;
- media presence/count/size matches the manifest.

This validation is a guardrail, not a replacement for trusting the backup source.

## 6. In-app restore

Requires **superuser**.

1. Open Backup & restore.
2. Select the `.bsbackup`.
3. Type `RESTORE` exactly.
4. Submit.

BSP then:

1. validates incoming backup;
2. creates a fresh safety `.bsbackup` of the current installation, including media only when the incoming backup includes media;
3. drops current tables/views in the configured BSP schema;
4. imports incoming `database.sql` using the receiving installation's own MySQL account;
5. runs the receiving BSP version's migrations;
6. runs Django system checks;
7. replaces MEDIA_ROOT when incoming media is present;
8. closes database connections and presents a standalone restore-complete page.

### Sessions after restore

A restore may replace the user/session tables that authenticated the request. Expect the current browser session to become invalid and log in with an identity contained in the restored database.

## 7. Automatic rollback

If restore fails after replacement begins, BSP attempts to restore the pre-operation safety backup automatically.

- If incoming restore fails but rollback succeeds, BSP reports that the previous database state was restored.
- If both restore and rollback fail, BSP surfaces both errors and the path of the safety backup for manual recovery.

Do not delete safety backups until the restored system has been validated.

## 8. Database-only restore behavior

A DB-only archive has no media directory. Restoring it **does not replace the receiving MEDIA_ROOT**.

This can create dangling file references if the incoming database references BAM/SHIT media that is not already present on the receiver. For dev → packaged migration, include media unless you intentionally know there are no required uploads.

## 9. Dev → packaged Windows migration test

Recommended end-to-end test:

### On development instance

1. Run the test suite.
2. Create a full `.bsbackup` with media included.
3. Keep a second copy outside the repo/workstation if the data matters.

### On target/fresh packaged install

1. Run `BS-Portal-v0.2.0-alpha-Setup.exe`.
2. Let Setup provision private `BSPortalMySQL` on `127.0.0.1:33069`.
3. When BSP opens `/setup/`, choose **Restore portable backup** instead of creating a temporary admin.
4. Select the dev `.bsbackup`.
5. Type `RESTORE`.
6. Wait for restore/migrations/check to complete.
7. Log in with the restored dev identity.

### Validate after migration

Verify at minimum:

- user identities and department memberships;
- BAM asset count and several known asset records;
- custody/history;
- BAMR requests, queue positions, reservations, active/returned checkouts;
- SHIT ticket count, Board state, ticket asset links, comments/attachments;
- BAM evidence files open successfully;
- Timeclock punches/corrections;
- About page reports the expected BSP version;
- `BS-Portal.exe --maintenance check` succeeds;
- new backup can be created from the packaged installation.

## 10. Source CLI import

```powershell
.\.venv\Scripts\python.exe portal\manage.py import_portal_backup .\path\backup.bsbackup --yes-really-restore --settings=config.settings.local
```

The explicit confirmation flag exists because import replaces current application data.

## 11. Backup storage locations

### Source development

Default:

```text
<repo>\data\backups\
```

Override with `BS_PORTAL_BACKUP_DIR`.

### Packaged Windows

```text
%ProgramData%\B.S. Supply Co\B.S. Portal\backups\
```

The Backup & restore page lists recent saved `.bsbackup` files and lets a superuser download them.

## 12. Installer safety backups

The packaged installer/maintenance migration flow creates a **database-only `.bsbackup`** before applying release migrations. Release migrations do not mutate uploaded media, so duplicating potentially large media trees for every installer upgrade is intentionally avoided.

For disaster recovery or machine migration, create a normal full backup with media.

## 13. Recovery rules

- Never test restore for the first time on your only copy of valuable data.
- Keep at least one backup outside the current BSP ProgramData/repository tree.
- Verify restored attachments/evidence, not just database row counts.
- An archive made by a newer BSP version must be restored into the same or newer BSP version; upgrade the receiver instead of bypassing the version check.
- Preserve the safety backup created before a restore until validation is complete.
