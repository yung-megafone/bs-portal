"""Settings for the packaged, localhost-only Windows desktop build."""

from pathlib import Path
import os
import sys

from .base import *  # noqa: F403,F401

DESKTOP_MODE = True
DEBUG = False

SECRET_KEY = env("DJANGO_SECRET_KEY")  # noqa: F405
if not SECRET_KEY:
    raise RuntimeError("DJANGO_SECRET_KEY was not loaded from the desktop runtime configuration")

ALLOWED_HOSTS = ["127.0.0.1", "localhost"]

_server_port = env("BS_PORTAL_SERVER_PORT", "8765")  # noqa: F405
CSRF_TRUSTED_ORIGINS = [
    f"http://127.0.0.1:{_server_port}",
    f"http://localhost:{_server_port}",
]

SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_HSTS_SECONDS = 0

STATIC_URL = "/static/"
if getattr(sys, "frozen", False):
    STATIC_ROOT = Path(sys._MEIPASS) / "staticfiles"  # type: ignore[attr-defined]
    STATICFILES_DIRS = []
else:
    STATIC_ROOT = REPO_DIR / ".desktop_staticfiles"  # noqa: F405

MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")  # noqa: F405
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

DATA_DIR = Path(env("BS_PORTAL_DATA_DIR", str(REPO_DIR / "data")))  # noqa: F405
MEDIA_ROOT = Path(env("BAM_MEDIA_ROOT", str(DATA_DIR / "media")))  # noqa: F405

LOG_DIR = DATA_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "{asctime} {levelname} {name}: {message}",
            "style": "{",
        }
    },
    "handlers": {
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOG_DIR / "bs-portal.log"),
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 5,
            "encoding": "utf-8",
            "formatter": "standard",
        }
    },
    "root": {"handlers": ["file"], "level": "INFO"},
    "loggers": {
        "django": {"handlers": ["file"], "level": "INFO", "propagate": False},
    },
}
