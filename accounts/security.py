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


def _password_reset_throttle():
    """Build the reset throttle from current settings so tests can override them."""
    return Throttle(
        namespace='accounts.password_reset',
        limit=settings.PASSWORD_RESET_RATE_LIMIT_IDENTITY_ATTEMPTS,
        window_seconds=settings.PASSWORD_RESET_RATE_LIMIT_WINDOW_SECONDS,
        ip_limit=settings.PASSWORD_RESET_RATE_LIMIT_IP_ATTEMPTS,
    )


def password_reset_is_throttled(request, email):
    return _password_reset_throttle().is_throttled(request, email)


def record_password_reset_request(request, email):
    _password_reset_throttle().record(request, email)
