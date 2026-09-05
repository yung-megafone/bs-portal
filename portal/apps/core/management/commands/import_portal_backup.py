from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.core.database_backups import DatabaseBackupError, restore_portable_backup


class Command(BaseCommand):
    help = "Restore a portable B.S. Portal .bsbackup archive into the configured MySQL database."

    def add_arguments(self, parser):
        parser.add_argument("backup", help="path to a .bsbackup archive")
        parser.add_argument(
            "--yes-really-restore",
            action="store_true",
            help="required acknowledgement that the configured database will be replaced",
        )

    def handle(self, *args, **options):
        if not options["yes_really_restore"]:
            raise CommandError("Refusing restore without --yes-really-restore.")
        try:
            safety, manifest = restore_portable_backup(Path(options["backup"]))
        except DatabaseBackupError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(
            self.style.SUCCESS(
                f"Restore complete from BSP {manifest.get('portal_version', 'unknown')}; safety backup: {safety}"
            )
        )
