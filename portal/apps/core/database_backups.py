"""Portable MySQL backup/restore helpers for B.S. Portal.

The portable ``.bsbackup`` format intentionally contains no database
credentials. It packages a mysqldump SQL stream plus a small manifest and,
optionally, the application's uploaded media directory. This makes the same
backup usable between a development checkout and the packaged Windows build.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tempfile
from typing import BinaryIO, Iterable
import zipfile

from django.conf import settings
from django.core.management import call_command
from django.db import connection, connections

from apps.core.version import __version__


BACKUP_FORMAT = "bs-portal-backup"
BACKUP_FORMAT_VERSION = 1
MAX_ARCHIVE_MEMBER_BYTES = 4 * 1024 * 1024 * 1024  # 4 GiB per member
MAX_ARCHIVE_TOTAL_BYTES = 16 * 1024 * 1024 * 1024  # 16 GiB uncompressed


class DatabaseBackupError(RuntimeError):
    """Raised for expected backup/restore failures that should be user-facing."""


@dataclass(frozen=True)
class BackupManifest:
    portal_version: str
    created_at: str
    sql_sha256: str
    includes_media: bool
    media_files: int = 0
    media_bytes: int = 0
    source_database: str = ""

    def as_dict(self) -> dict:
        return {
            "format": BACKUP_FORMAT,
            "format_version": BACKUP_FORMAT_VERSION,
            "portal_version": self.portal_version,
            "created_at": self.created_at,
            "database_engine": "mysql",
            "source_database": self.source_database,
            "sql_sha256": self.sql_sha256,
            "includes_media": self.includes_media,
            "media_files": self.media_files,
            "media_bytes": self.media_bytes,
        }


@dataclass(frozen=True)
class ValidatedBackup:
    archive_path: Path
    working_dir: Path
    sql_path: Path
    media_dir: Path | None
    manifest: dict


# ---------------------------------------------------------------------------
# Runtime paths / executables
# ---------------------------------------------------------------------------


def backup_storage_dir() -> Path:
    configured = os.environ.get("BS_PORTAL_BACKUP_DIR")
    if configured:
        path = Path(configured)
    elif getattr(settings, "DESKTOP_MODE", False):
        data_dir = Path(os.environ.get("BS_PORTAL_DATA_DIR", settings.BASE_DIR.parent / "data"))
        path = data_dir / "backups"
    else:
        path = settings.BASE_DIR.parent / "data" / "backups"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _candidate_mysql_bin_dirs() -> Iterable[Path]:
    configured = os.environ.get("MYSQL_BIN_DIR") or os.environ.get("BS_PORTAL_MYSQL_BIN_DIR")
    if configured:
        yield Path(configured)

    if os.name == "nt":
        program_files = [os.environ.get("ProgramFiles"), os.environ.get("ProgramW6432")]
        for root in filter(None, program_files):
            base = Path(root) / "MySQL"
            for name in (
                "MySQL Server 8.4",
                "MySQL Server 8.0",
                "MySQL Server 9.0",
            ):
                yield base / name / "bin"


def _find_mysql_tool(name: str) -> Path:
    executable = f"{name}.exe" if os.name == "nt" else name
    via_path = shutil.which(executable) or shutil.which(name)
    if via_path:
        return Path(via_path)

    for directory in _candidate_mysql_bin_dirs():
        candidate = directory / executable
        if candidate.exists():
            return candidate

    raise DatabaseBackupError(
        f"{executable} could not be found. Install a compatible MySQL client or set MYSQL_BIN_DIR."
    )


def _db_config() -> dict:
    db = settings.DATABASES["default"]
    if db.get("ENGINE") != "django.db.backends.mysql":
        raise DatabaseBackupError("Portable backup/restore currently supports the MySQL backend only.")
    return {
        "name": str(db.get("NAME", "")),
        "user": str(db.get("USER", "")),
        "password": str(db.get("PASSWORD", "")),
        "host": str(db.get("HOST", "127.0.0.1")),
        "port": str(db.get("PORT", "3306")),
    }


def _subprocess_env(db: dict) -> dict:
    env = os.environ.copy()
    # MySQL documents MYSQL_PWD as less preferred than an option file, but it
    # avoids putting the password in the process command line. The child is
    # short-lived and receives only the application database credential.
    env["MYSQL_PWD"] = db["password"]
    return env


def _creationflags() -> int:
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


def dump_database(destination: Path) -> Path:
    db = _db_config()
    mysqldump = _find_mysql_tool("mysqldump")
    destination.parent.mkdir(parents=True, exist_ok=True)

    command = [
        str(mysqldump),
        f"--host={db['host']}",
        f"--port={db['port']}",
        f"--user={db['user']}",
        "--protocol=tcp",
        "--single-transaction",
        "--skip-lock-tables",
        "--no-tablespaces",
        "--set-gtid-purged=OFF",
        "--triggers",
        "--default-character-set=utf8mb4",
        "--hex-blob",
        db["name"],
    ]

    with destination.open("wb") as output:
        result = subprocess.run(
            command,
            stdout=output,
            stderr=subprocess.PIPE,
            env=_subprocess_env(db),
            creationflags=_creationflags(),
        )

    if result.returncode != 0:
        destination.unlink(missing_ok=True)
        error = result.stderr.decode("utf-8", errors="replace").strip()
        raise DatabaseBackupError(f"mysqldump failed: {error or 'unknown error'}")

    if not destination.exists() or destination.stat().st_size == 0:
        destination.unlink(missing_ok=True)
        raise DatabaseBackupError("mysqldump completed without producing database content.")

    return destination


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _media_stats(media_root: Path) -> tuple[int, int]:
    count = 0
    total = 0
    if not media_root.exists():
        return count, total
    for path in media_root.rglob("*"):
        if path.is_file():
            count += 1
            total += path.stat().st_size
    return count, total


def create_portable_backup(*, include_media: bool = True, destination: Path | None = None) -> Path:
    timestamp = datetime.now(timezone.utc)
    safe_stamp = timestamp.strftime("%Y%m%d-%H%M%S")
    destination = destination or backup_storage_dir() / f"bs-portal-{safe_stamp}.bsbackup"
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="bsportal-backup-") as temp_name:
        temp_dir = Path(temp_name)
        sql_path = dump_database(temp_dir / "database.sql")
        sql_hash = _sha256_file(sql_path)

        media_root = Path(settings.MEDIA_ROOT)
        media_files, media_bytes = _media_stats(media_root) if include_media else (0, 0)
        manifest = BackupManifest(
            portal_version=__version__,
            created_at=timestamp.isoformat(),
            sql_sha256=sql_hash,
            includes_media=bool(include_media),
            media_files=media_files,
            media_bytes=media_bytes,
            source_database=_db_config()["name"],
        )

        temp_archive = destination.with_suffix(destination.suffix + ".new")
        temp_archive.unlink(missing_ok=True)
        try:
            with zipfile.ZipFile(temp_archive, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as archive:
                archive.writestr(
                    "manifest.json",
                    json.dumps(manifest.as_dict(), indent=2, sort_keys=True).encode("utf-8"),
                )
                archive.write(sql_path, "database.sql")
                if include_media and media_root.exists():
                    for path in sorted(media_root.rglob("*")):
                        if path.is_file():
                            relative = path.relative_to(media_root).as_posix()
                            archive.write(path, f"media/{relative}")
            os.replace(temp_archive, destination)
        finally:
            temp_archive.unlink(missing_ok=True)

    return destination


# ---------------------------------------------------------------------------
# Validation / extraction
# ---------------------------------------------------------------------------


def _version_tuple(value: str) -> tuple[int, int, int]:
    core = (value or "0.0.0").split("-", 1)[0]
    parts = core.split(".")
    parsed: list[int] = []
    for item in parts[:3]:
        try:
            parsed.append(int(item))
        except ValueError:
            parsed.append(0)
    while len(parsed) < 3:
        parsed.append(0)
    return tuple(parsed)  # type: ignore[return-value]


def _safe_member_path(name: str) -> PurePosixPath:
    if "\\" in name or ":" in name or "\x00" in name:
        raise DatabaseBackupError(f"Backup archive contains an unsafe path: {name!r}")
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or any(part in {"", "."} for part in path.parts):
        raise DatabaseBackupError(f"Backup archive contains an unsafe path: {name!r}")
    return path


def _member_is_symlink(info: zipfile.ZipInfo) -> bool:
    unix_mode = (info.external_attr >> 16) & 0xFFFF
    return (unix_mode & 0o170000) == 0o120000


def _copy_zip_member(archive: zipfile.ZipFile, info: zipfile.ZipInfo, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with archive.open(info, "r") as source, destination.open("wb") as target:
        shutil.copyfileobj(source, target, length=1024 * 1024)


def validate_and_extract_backup(archive_path: Path, working_dir: Path) -> ValidatedBackup:
    archive_path = Path(archive_path)
    if not archive_path.exists():
        raise DatabaseBackupError("The backup file does not exist.")
    if not zipfile.is_zipfile(archive_path):
        raise DatabaseBackupError("The selected file is not a valid B.S. Portal backup archive.")

    working_dir.mkdir(parents=True, exist_ok=True)
    total_uncompressed = 0
    names: set[str] = set()

    try:
        with zipfile.ZipFile(archive_path, "r") as archive:
            for info in archive.infolist():
                if info.is_dir():
                    continue
                if _member_is_symlink(info):
                    raise DatabaseBackupError("Backup archives may not contain symbolic links.")
                member = _safe_member_path(info.filename)
                name = member.as_posix()
                if name in names:
                    raise DatabaseBackupError(f"Backup archive contains a duplicate member: {name}")
                names.add(name)
                if info.file_size > MAX_ARCHIVE_MEMBER_BYTES:
                    raise DatabaseBackupError(f"Backup member is too large: {name}")
                total_uncompressed += info.file_size
                if total_uncompressed > MAX_ARCHIVE_TOTAL_BYTES:
                    raise DatabaseBackupError("Backup archive expands beyond the supported size limit.")
                if name not in {"manifest.json", "database.sql"} and not name.startswith("media/"):
                    raise DatabaseBackupError(f"Unexpected file in backup archive: {name}")

            if "manifest.json" not in names or "database.sql" not in names:
                raise DatabaseBackupError("Backup archive is missing manifest.json or database.sql.")

            manifest_info = archive.getinfo("manifest.json")
            if manifest_info.file_size > 1024 * 1024:
                raise DatabaseBackupError("Backup manifest is unexpectedly large.")
            manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
            if manifest.get("format") != BACKUP_FORMAT:
                raise DatabaseBackupError("This archive is not a B.S. Portal portable backup.")
            if manifest.get("format_version") != BACKUP_FORMAT_VERSION:
                raise DatabaseBackupError(
                    f"Unsupported backup format version: {manifest.get('format_version')!r}."
                )
            if manifest.get("database_engine") != "mysql":
                raise DatabaseBackupError("The backup was not created from the MySQL backend.")
            source_version = str(manifest.get("portal_version", "0.0.0"))
            if _version_tuple(source_version) > _version_tuple(__version__):
                raise DatabaseBackupError(
                    f"This backup was created by B.S. Portal {source_version}, which is newer than the running {__version__}. "
                    "Upgrade B.S. Portal before restoring it."
                )

            sql_path = working_dir / "database.sql"
            _copy_zip_member(archive, archive.getinfo("database.sql"), sql_path)
            actual_hash = _sha256_file(sql_path)
            expected_hash = str(manifest.get("sql_sha256", ""))
            if not expected_hash or actual_hash.lower() != expected_hash.lower():
                raise DatabaseBackupError("Database SQL integrity check failed.")

            _validate_sql_scope(sql_path)

            includes_media = bool(manifest.get("includes_media"))
            media_members = [info for info in archive.infolist() if info.filename.startswith("media/") and not info.is_dir()]
            if not includes_media and media_members:
                raise DatabaseBackupError("Backup manifest says media is excluded, but media files are present.")

            media_dir: Path | None = None
            if includes_media:
                media_dir = working_dir / "media"
                media_dir.mkdir(parents=True, exist_ok=True)
                for info in media_members:
                    member = _safe_member_path(info.filename)
                    relative = PurePosixPath(*member.parts[1:])
                    if not relative.parts:
                        continue
                    destination = media_dir.joinpath(*relative.parts)
                    _copy_zip_member(archive, info, destination)

                actual_files, actual_bytes = _media_stats(media_dir)
                expected_files = int(manifest.get("media_files", 0) or 0)
                expected_bytes = int(manifest.get("media_bytes", 0) or 0)
                if actual_files != expected_files or actual_bytes != expected_bytes:
                    raise DatabaseBackupError("Backup media integrity metadata does not match the archive contents.")

    except DatabaseBackupError:
        raise
    except (zipfile.BadZipFile, json.JSONDecodeError, UnicodeDecodeError, KeyError) as exc:
        raise DatabaseBackupError(f"Backup archive validation failed: {exc}") from exc

    return ValidatedBackup(
        archive_path=archive_path,
        working_dir=working_dir,
        sql_path=sql_path,
        media_dir=media_dir,
        manifest=manifest,
    )


def _validate_sql_scope(sql_path: Path) -> None:
    # mysqldump output should contain schema/data for the selected DB, not
    # server-level administration statements. This is a guardrail, not a SQL
    # parser; restore is superuser-only and still relies on MySQL privileges.
    prohibited = (
        b"CREATE DATABASE",
        b"DROP DATABASE",
        b"CREATE USER",
        b"ALTER USER",
        b"DROP USER",
        b"GRANT ",
        b"REVOKE ",
        b"INSTALL PLUGIN",
        b"UNINSTALL PLUGIN",
    )
    with sql_path.open("rb") as handle:
        for raw_line in handle:
            stripped = raw_line.lstrip().upper()
            if any(stripped.startswith(token) for token in prohibited):
                raise DatabaseBackupError(
                    "Backup SQL contains server-level administrative statements and will not be restored."
                )


# ---------------------------------------------------------------------------
# Restore
# ---------------------------------------------------------------------------


def _drop_current_schema() -> None:
    # Use the current authenticated application connection before closing all
    # ORM connections. The application user owns only the BSP database in the
    # packaged build.
    with connection.cursor() as cursor:
        cursor.execute("SET FOREIGN_KEY_CHECKS=0")
        cursor.execute("SHOW FULL TABLES WHERE Table_type = 'BASE TABLE'")
        tables = [row[0] for row in cursor.fetchall()]
        for table in tables:
            escaped = str(table).replace("`", "``")
            cursor.execute(f"DROP TABLE IF EXISTS `{escaped}`")
        cursor.execute("SHOW FULL TABLES WHERE Table_type = 'VIEW'")
        views = [row[0] for row in cursor.fetchall()]
        for view in views:
            escaped = str(view).replace("`", "``")
            cursor.execute(f"DROP VIEW IF EXISTS `{escaped}`")
        cursor.execute("SET FOREIGN_KEY_CHECKS=1")


def _import_sql(sql_path: Path) -> None:
    db = _db_config()
    mysql = _find_mysql_tool("mysql")
    command = [
        str(mysql),
        f"--host={db['host']}",
        f"--port={db['port']}",
        f"--user={db['user']}",
        "--protocol=tcp",
        "--default-character-set=utf8mb4",
        db["name"],
    ]
    with sql_path.open("rb") as source:
        result = subprocess.run(
            command,
            stdin=source,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=_subprocess_env(db),
            creationflags=_creationflags(),
        )
    if result.returncode != 0:
        error = result.stderr.decode("utf-8", errors="replace").strip()
        raise DatabaseBackupError(f"mysql restore failed: {error or 'unknown error'}")


def _replace_media_from_directory(source_media: Path) -> None:
    media_root = Path(settings.MEDIA_ROOT)
    parent = media_root.parent
    parent.mkdir(parents=True, exist_ok=True)
    old_media = parent / f"{media_root.name}.restore-old-{os.getpid()}"
    if old_media.exists():
        shutil.rmtree(old_media)

    try:
        if media_root.exists():
            os.replace(media_root, old_media)
        media_root.mkdir(parents=True, exist_ok=True)
        if source_media.exists():
            for path in source_media.rglob("*"):
                relative = path.relative_to(source_media)
                destination = media_root / relative
                if path.is_dir():
                    destination.mkdir(parents=True, exist_ok=True)
                elif path.is_file():
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(path, destination)
    except Exception:
        if media_root.exists():
            shutil.rmtree(media_root, ignore_errors=True)
        if old_media.exists():
            os.replace(old_media, media_root)
        raise
    else:
        if old_media.exists():
            shutil.rmtree(old_media, ignore_errors=True)


def _restore_validated_backup(validated: ValidatedBackup, *, run_migrations: bool = True) -> None:
    _drop_current_schema()
    connections.close_all()
    _import_sql(validated.sql_path)
    connections.close_all()

    if run_migrations:
        call_command("migrate", interactive=False, verbosity=0)
        call_command("check", verbosity=0)

    if validated.media_dir is not None:
        _replace_media_from_directory(validated.media_dir)

    connections.close_all()


def restore_portable_backup(archive_path: Path) -> tuple[Path, dict]:
    """Restore a portable backup and return ``(safety_backup, manifest)``.

    A new safety backup of the current state is created before any destructive
    action. If the incoming restore fails, BSP attempts to put that safety
    backup back automatically before surfacing the error.
    """

    archive_path = Path(archive_path)
    with tempfile.TemporaryDirectory(prefix="bsportal-restore-incoming-") as incoming_name:
        incoming = validate_and_extract_backup(archive_path, Path(incoming_name))
        safety_backup = create_portable_backup(include_media=incoming.media_dir is not None)

        try:
            _restore_validated_backup(incoming, run_migrations=True)
        except Exception as restore_exc:
            rollback_error: Exception | None = None
            try:
                with tempfile.TemporaryDirectory(prefix="bsportal-restore-rollback-") as rollback_name:
                    rollback = validate_and_extract_backup(safety_backup, Path(rollback_name))
                    _restore_validated_backup(rollback, run_migrations=False)
            except Exception as exc:  # pragma: no cover - catastrophic recovery path
                rollback_error = exc

            if rollback_error is not None:
                raise DatabaseBackupError(
                    "The requested restore failed and automatic rollback also failed. "
                    f"Restore error: {restore_exc}. Rollback error: {rollback_error}. "
                    f"Safety backup: {safety_backup}"
                ) from restore_exc

            raise DatabaseBackupError(
                f"Restore failed and the previous database state was restored automatically: {restore_exc}"
            ) from restore_exc

        return safety_backup, incoming.manifest


def list_saved_backups(*, limit: int = 20) -> list[dict]:
    rows: list[dict] = []
    for path in sorted(backup_storage_dir().glob("*.bsbackup"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]:
        stat = path.stat()
        rows.append(
            {
                "name": path.name,
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
            }
        )
    return rows


def saved_backup_path(name: str) -> Path:
    candidate = Path(name).name
    if candidate != name or not candidate.endswith(".bsbackup"):
        raise DatabaseBackupError("Invalid backup filename.")
    path = backup_storage_dir() / candidate
    if not path.exists() or not path.is_file():
        raise DatabaseBackupError("Backup file was not found.")
    return path
