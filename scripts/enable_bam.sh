#!/usr/bin/env bash
set -euo pipefail
[ -f portal/manage.py ] || { echo "Run this script from the B.S. Portal repository root." >&2; exit 1; }
python portal/manage.py check
python portal/manage.py makemigrations bam
python portal/manage.py migrate
python portal/manage.py seed_bam
python portal/manage.py check
echo "BAM enabled. Start Portal with: python portal/manage.py runserver"
