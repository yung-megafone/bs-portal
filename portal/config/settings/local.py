from .base import *  # noqa: F403,F401

DEBUG = env_bool("DJANGO_DEBUG", True)  # noqa: F405
SECRET_KEY = env("DJANGO_SECRET_KEY", "unsafe-local-only-secret-key")  # noqa: F405
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", ["127.0.0.1", "localhost"])  # noqa: F405
CSRF_TRUSTED_ORIGINS = env_list(  # noqa: F405
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    ["http://127.0.0.1:8000", "http://localhost:8000"],
)
