from .base import *  # noqa: F403,F401

DEBUG = False
SECRET_KEY = env("DJANGO_SECRET_KEY")  # noqa: F405
if not SECRET_KEY:
    raise RuntimeError("DJANGO_SECRET_KEY must be set in production")

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", ["portal.bssply.co"])  # noqa: F405
CSRF_TRUSTED_ORIGINS = env_list(  # noqa: F405
    "DJANGO_CSRF_TRUSTED_ORIGINS", ["https://portal.bssply.co"]
)

SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
