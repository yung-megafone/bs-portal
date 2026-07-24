from .base import *  # noqa: F403,F401

DEBUG = False
SECRET_KEY = "test-only-secret-key"
ALLOWED_HOSTS = ["testserver", "localhost"]

DATABASES["default"].update(  # noqa: F405
    {
        "NAME": env("TEST_MYSQL_DATABASE", env("MYSQL_DATABASE", "bs_portal_dev")),  # noqa: F405
        "USER": env("TEST_MYSQL_USER", env("MYSQL_USER", "bs_portal")),  # noqa: F405
        "PASSWORD": env("TEST_MYSQL_PASSWORD", env("MYSQL_PASSWORD", "")),  # noqa: F405
        "HOST": env("TEST_MYSQL_HOST", env("MYSQL_HOST", "127.0.0.1")),  # noqa: F405
        "PORT": env("TEST_MYSQL_PORT", env("MYSQL_PORT", "3306")),  # noqa: F405
        "CONN_MAX_AGE": 0,
    }
)

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
