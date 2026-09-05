from django.core.management.base import BaseCommand, CommandError

from apps.core.database_backups import DatabaseBackupError, create_portable_backup


class Command(BaseCommand):
    help = "Create a portable B.S. Portal .bsbackup archive."

    def add_arguments(self, parser):
        parser.add_argument("--database-only", action="store_true", help="exclude uploaded media files")
        parser.add_argument("--output", help="optional destination .bsbackup path")

    def handle(self, *args, **options):
        try:
            path = create_portable_backup(
                include_media=not options["database_only"],
                destination=options.get("output") or None,
            )
        except DatabaseBackupError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(str(path)))
