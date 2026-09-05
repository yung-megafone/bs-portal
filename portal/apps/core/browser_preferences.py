"""Browser-local UI preferences shared across portal modules.

These values intentionally contain presentation choices only. They are readable by
JavaScript and are not an authorization source. Server-side code must always
validate a preference before using it.
"""

COOKIE_PREFIX = "bs-portal-pref-"
PREFERENCE_MAX_AGE = 60 * 60 * 24 * 365


def cookie_name(name):
    return f"{COOKIE_PREFIX}{name}"


def get_preference(request, name, *, allowed, default):
    value = request.COOKIES.get(cookie_name(name))
    return value if value in allowed else default


def set_preference_cookie(response, request, name, value):
    response.set_cookie(
        cookie_name(name),
        value,
        max_age=PREFERENCE_MAX_AGE,
        path="/",
        secure=request.is_secure(),
        httponly=False,
        samesite="Lax",
    )
    return response
