from django.core.management.base import BaseCommand

from apps.bam.services import process_due_bam_automation


class Command(BaseCommand):
    help = "Run one BAM automation pulse for pending approvals, queued-request reconciliation, and due automatic custody transfers."

    def handle(self, *args, **options):
        counts = process_due_bam_automation()
        self.stdout.write(
            self.style.SUCCESS(
                "BAM automation pulse: "
                + ", ".join(f"{key}={value}" for key, value in counts.items())
            )
        )
