from django.core.management.base import BaseCommand

from apps.departments.models import Department
from apps.bam.models import AssetStatus, AssetType


TYPES = {
    "R": "Radio",
    "B": "Battery",
    "L": "Laptop",
    "D": "Desktop",
    "S": "Server",
    "N": "Network Equipment",
    "P": "Phone",
    "T": "Tablet",
    "M": "Monitor",
    "C": "Camera",
    "V": "Vehicle Equipment",
    "H": "Headset",
    "K": "Keyboard",
    "X": "Charger / Power Supply",
    "F": "File / Document",
    "O": "Other",
}

STATUSES = [
    ("ACTIVE", "Active", False, 10),
    ("RESERVED", "Reserved", False, 20),
    ("STORAGE", "Storage", False, 30),
    ("REPAIR", "Repair", False, 40),
    ("LOST", "Lost", False, 50),
    ("RETIRED", "Retired", True, 90),
    ("DISPOSED", "Disposed", True, 100),
]


class Command(BaseCommand):
    help = "Seed BAM asset types/statuses and the SR69 department if absent."

    def handle(self, *args, **options):
        for code, name in TYPES.items():
            AssetType.objects.get_or_create(code=code, defaults={"name": name})
        for code, name, terminal, order in STATUSES:
            AssetStatus.objects.get_or_create(
                code=code,
                defaults={"name": name, "is_terminal": terminal, "sort_order": order},
            )
        Department.objects.get_or_create(
            code="SR69",
            defaults={"name": "SubRosa69", "description": "Communications research and systems engineering division."},
        )
        self.stdout.write(self.style.SUCCESS("BAM reference data seeded."))
