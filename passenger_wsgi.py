"""cPanel/Passenger WSGI entry point for B.S. Portal."""
from pathlib import Path
import os
import sys

ROOT = Path(__file__).resolve().parent
PORTAL_DIR = ROOT / "portal"
if str(PORTAL_DIR) not in sys.path:
    sys.path.insert(0, str(PORTAL_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.staging")

from config.wsgi import application  # noqa: E402,F401
