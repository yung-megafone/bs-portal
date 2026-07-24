"""Seed synthetic alpha data.

Run with:
    python portal/manage.py shell < scripts/seed_demo_data.py
"""
from apps.departments.models import Department

for code, name, description in [
    ("CORP", "Corporate", "Company-wide administration and governance."),
    ("OPS", "Operations", "General operational functions."),
    ("SR69", "SubRosa69", "Communications research and systems engineering."),
    ("NSEC", "NSEC", "Security and compliance functions."),
]:
    Department.objects.get_or_create(code=code, defaults={"name": name, "description": description})

print("Synthetic department seed complete.")
