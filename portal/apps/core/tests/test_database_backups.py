import hashlib
import json
from pathlib import Path
import tempfile
from unittest.mock import patch
import zipfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from apps.core.database_backups import (
    BACKUP_FORMAT,
    BACKUP_FORMAT_VERSION,
    DatabaseBackupError,
    create_portable_backup,
    validate_and_extract_backup,
)
from apps.core.forms import PortalBackupImportForm
from apps.identity.models import User


class BackupArchiveTests(SimpleTestCase):
    def _write_archive(self, root: Path, *, portal_version="0.2.0-alpha", sql=b"SELECT 1;\n", includes_media=False):
        sql_hash = hashlib.sha256(sql).hexdigest()
        manifest = {
            "format": BACKUP_FORMAT,
            "format_version": BACKUP_FORMAT_VERSION,
            "portal_version": portal_version,
            "created_at": "2026-09-05T12:00:00+00:00",
            "database_engine": "mysql",
            "source_database": "bs_portal_dev",
            "sql_sha256": sql_hash,
            "includes_media": includes_media,
            "media_files": 0,
            "media_bytes": 0,
        }
        archive_path = root / "test.bsbackup"
        with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("manifest.json", json.dumps(manifest))
            archive.writestr("database.sql", sql)
        return archive_path

    def test_valid_archive_extracts_and_verifies_hash(self):
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            archive = self._write_archive(root)
            validated = validate_and_extract_backup(archive, root / "work")
            self.assertEqual(validated.sql_path.read_bytes(), b"SELECT 1;\n")
            self.assertEqual(validated.manifest["format"], BACKUP_FORMAT)

    def test_newer_portal_backup_is_refused(self):
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            archive = self._write_archive(root, portal_version="99.0.0")
            with self.assertRaisesMessage(DatabaseBackupError, "newer than"):
                validate_and_extract_backup(archive, root / "work")

    def test_sql_hash_mismatch_is_refused(self):
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            archive = self._write_archive(root)
            with zipfile.ZipFile(archive, "a", zipfile.ZIP_DEFLATED) as output:
                output.writestr("database.sql", b"tampered\n")
            with self.assertRaises(DatabaseBackupError):
                validate_and_extract_backup(archive, root / "work")

    def test_restore_confirmation_must_be_exact(self):
        upload = SimpleUploadedFile("backup.bsbackup", b"content")
        form = PortalBackupImportForm(
            data={"confirmation": "restore"},
            files={"backup": upload},
        )
        self.assertFalse(form.is_valid())
        self.assertIn("confirmation", form.errors)

    @override_settings(MEDIA_ROOT="/tmp/bsportal-nonexistent-media")
    def test_export_archive_can_be_database_only(self):
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            destination = root / "export.bsbackup"

            def fake_dump(path):
                Path(path).write_bytes(b"-- test dump\nSELECT 1;\n")
                return Path(path)

            with patch("apps.core.database_backups.dump_database", side_effect=fake_dump):
                path = create_portable_backup(include_media=False, destination=destination)

            with zipfile.ZipFile(path, "r") as archive:
                manifest = json.loads(archive.read("manifest.json"))
                self.assertFalse(manifest["includes_media"])
                self.assertIn("database.sql", archive.namelist())
                self.assertFalse(any(name.startswith("media/") for name in archive.namelist()))


class DataManagementViewTests(TestCase):
    def setUp(self):
        self.regular = User.objects.create_user(username="regular", password="test-password-123")
        self.admin = User.objects.create_superuser(
            username="admin",
            email="",
            password="test-password-123",
        )

    def test_regular_user_cannot_open_data_management(self):
        self.client.login(username="regular", password="test-password-123")
        response = self.client.get(reverse("data_management"))
        self.assertEqual(response.status_code, 403)

    def test_superuser_can_open_data_management(self):
        self.client.login(username="admin", password="test-password-123")
        response = self.client.get(reverse("data_management"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Backup &amp; restore")

    def test_export_returns_created_portable_backup(self):
        self.client.login(username="admin", password="test-password-123")
        with tempfile.TemporaryDirectory() as temp_name:
            path = Path(temp_name) / "bs-portal-test.bsbackup"
            path.write_bytes(b"portable-backup")
            with patch("apps.core.views.create_portable_backup", return_value=path) as create:
                response = self.client.post(reverse("export_portal_backup"), {"include_media": "on"})

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response["X-BS-Portal-Backup"], "portable")
            create.assert_called_once_with(include_media=True)

    def test_import_calls_restore_after_confirmation(self):
        self.client.login(username="admin", password="test-password-123")
        upload = SimpleUploadedFile("dev-data.bsbackup", b"portable")
        with tempfile.TemporaryDirectory() as temp_name:
            safety = Path(temp_name) / "safety.bsbackup"
            with patch(
                "apps.core.views.restore_portable_backup",
                return_value=(safety, {"portal_version": "0.2.0-alpha"}),
            ) as restore:
                response = self.client.post(
                    reverse("import_portal_backup"),
                    {"confirmation": "RESTORE", "backup": upload},
                )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Restore complete")
        restore.assert_called_once()
