from .base import *  # noqa: F403,F401

DEBUG = False
SECRET_KEY = "test-only-secret-key"
ALLOWED_HOSTS = ["testserver", "localhost"]

DATABASES["default"].update(  # noqa: F405
    {
        "NAME": env("TEST_POSTGRES_DB", env("POSTGRES_DB", "bs_portal_dev")),  # noqa: F405
        "USER": env("TEST_POSTGRES_USER", env("POSTGRES_USER", "bs_portal")),  # noqa: F405
        "PASSWORD": env("TEST_POSTGRES_PASSWORD", env("POSTGRES_PASSWORD", "")),  # noqa: F405
        "HOST": env("TEST_POSTGRES_HOST", env("POSTGRES_HOST", "127.0.0.1")),  # noqa: F405
        "PORT": env("TEST_POSTGRES_PORT", env("POSTGRES_PORT", "5432")),  # noqa: F405
        "CONN_MAX_AGE": 0,
    }
)

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
