"""Small cache-backed protections for public account endpoints."""
from django.conf import settings

from core.ratelimit import Throttle


def _login_throttle():
    """Build the throttle from current settings so tests can override them."""
    return Throttle(
        namespace='accounts.login',
        limit=settings.LOGIN_RATE_LIMIT_IDENTITY_ATTEMPTS,
        window_seconds=settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS,
        ip_limit=settings.LOGIN_RATE_LIMIT_IP_ATTEMPTS,
    )


def login_is_throttled(request, username):
    return _login_throttle().is_throttled(request, username)


def record_failed_login(request, username):
    _login_throttle().record(request, username)


def clear_login_failures(request, username):
    _login_throttle().clear(request, username)
