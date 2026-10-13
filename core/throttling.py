"""Throttle instances for the anonymously reachable write endpoints."""
from django.conf import settings

from core.ratelimit import Throttle


def get_throttle(namespace):
    """Return the configured :class:`Throttle` for a public write endpoint.

    An unknown namespace falls back to a conservative single limit instead of
    raising, so a typo in a view can never disable protection silently.
    """
    limit, ip_limit = settings.PUBLIC_WRITE_RATE_LIMITS.get(namespace, (5, 20))
    return Throttle(
        namespace=f'public.{namespace}',
        limit=limit,
        window_seconds=settings.PUBLIC_WRITE_RATE_LIMIT_WINDOW_SECONDS,
        ip_limit=ip_limit,
    )
