"""Small cache-backed protections for public account endpoints."""
from hashlib import sha256

from django.conf import settings
from django.core.cache import cache


def _remote_address(request):
    """Use REMOTE_ADDR, not an untrusted X-Forwarded-For header.

    A reverse proxy may set REMOTE_ADDR to its own address; production should
    configure the proxy/WAF to enforce its own IP-aware rate limit as well.
    """
    return request.META.get('REMOTE_ADDR', 'unknown')


def _key(prefix, value):
    digest = sha256(value.encode('utf-8')).hexdigest()
    return f'accounts.login-throttle.{prefix}.{digest}'


def _keys(request, username):
    remote_address = _remote_address(request)
    normalized_username = (username or '').strip().casefold()
    return (
        _key('ip', remote_address),
        _key('identity', f'{remote_address}:{normalized_username}'),
    )


def _increment(key, window_seconds):
    if cache.add(key, 1, timeout=window_seconds):
        return 1
    try:
        return cache.incr(key)
    except ValueError:
        # A concurrent expiry is harmless: start a fresh window.
        cache.set(key, 1, timeout=window_seconds)
        return 1


def login_is_throttled(request, username):
    ip_key, identity_key = _keys(request, username)
    return (
        cache.get(ip_key, 0) >= settings.LOGIN_RATE_LIMIT_IP_ATTEMPTS
        or cache.get(identity_key, 0) >= settings.LOGIN_RATE_LIMIT_IDENTITY_ATTEMPTS
    )


def record_failed_login(request, username):
    ip_key, identity_key = _keys(request, username)
    window = settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS
    _increment(ip_key, window)
    _increment(identity_key, window)


def clear_login_failures(request, username):
    cache.delete_many(_keys(request, username))
