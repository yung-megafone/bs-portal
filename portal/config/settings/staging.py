from .base import *  # noqa: F403,F401

DEBUG = False
SECRET_KEY = env("DJANGO_SECRET_KEY")  # noqa: F405
if not SECRET_KEY:
    raise RuntimeError("DJANGO_SECRET_KEY must be set in staging")

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", ["dev.bssply.co"])  # noqa: F405
CSRF_TRUSTED_ORIGINS = env_list(  # noqa: F405
    "DJANGO_CSRF_TRUSTED_ORIGINS", ["https://dev.bssply.co"]
)

SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", True)  # noqa: F405
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 0  # Enable deliberately after HTTPS/proxy behavior is verified.

# Common cPanel/reverse-proxy configuration. If the host does not set
# X-Forwarded-Proto correctly, verify before relying on this value.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
