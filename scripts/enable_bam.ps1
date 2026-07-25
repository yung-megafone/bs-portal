$ErrorActionPreference = "Stop"
Write-Host "B.S. Portal BAM alpha setup" -ForegroundColor Cyan
if (-not (Test-Path "portal/manage.py")) {
    throw "Run this script from the B.S. Portal repository root."
}
python portal/manage.py check
python portal/manage.py makemigrations bam
python portal/manage.py migrate
python portal/manage.py seed_bam
python portal/manage.py check
Write-Host "BAM enabled. Start Portal with: python portal/manage.py runserver" -ForegroundColor Green
