"""Cache-backed throttling primitives shared by public write endpoints.

A shared cache (Redis/Memcached) makes a limit apply across every worker
process.  The default local-memory cache only covers a single process, which is
acceptable for a single-process deployment; the deployment guide documents
enabling the host's own rate limiting as well.

The client IP is read from ``REMOTE_ADDR`` rather than ``X-Forwarded-For``: the
latter is attacker-controlled unless a trusted proxy overwrites it.
"""
from hashlib import sha256

from django.core.cache import cache


def remote_address(request):
    """Best-effort client address without trusting forwarded headers."""
    return request.META.get('REMOTE_ADDR', 'unknown')


def _cache_key(namespace, value):
    digest = sha256(str(value).encode('utf-8')).hexdigest()
    return f'ratelimit.{namespace}.{digest}'


def _increment(key, window_seconds):
    if cache.add(key, 1, timeout=window_seconds):
        return 1
    try:
        return cache.incr(key)
    except ValueError:
        # A concurrent expiry is harmless: start a fresh window.
        cache.set(key, 1, timeout=window_seconds)
        return 1


class Throttle:
    """Count attempts per address and per ``address + identity`` pair.

    Two counters are kept because a single IP limit would block everyone behind
    one NAT, while a single identity limit would let an attacker rotate
    identities from one host.
    """

    def __init__(self, namespace, limit, window_seconds, ip_limit=None):
        self.namespace = namespace
        self.limit = limit
        self.window_seconds = window_seconds
        self.ip_limit = limit if ip_limit is None else ip_limit

    def keys_for(self, request, identity=''):
        address = remote_address(request)
        return (
            _cache_key(f'{self.namespace}.ip', address),
            _cache_key(f'{self.namespace}.identity',
                       f'{address}:{(identity or "").strip().casefold()}'),
        )

    def is_throttled(self, request, identity=''):
        ip_key, identity_key = self.keys_for(request, identity)
        return (
            cache.get(ip_key, 0) >= self.ip_limit
            or cache.get(identity_key, 0) >= self.limit
        )

    def record(self, request, identity=''):
        for key in self.keys_for(request, identity):
            _increment(key, self.window_seconds)

    def clear(self, request, identity=''):
        cache.delete_many(self.keys_for(request, identity))
