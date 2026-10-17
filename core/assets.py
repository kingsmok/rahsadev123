"""Cache-busting URLs for the project's own static files.

Static files are served under fixed names (no ManifestStaticFilesStorage) and
the PWA service worker answers ``/static/`` requests from its cache first, while
browsers may also keep such files "heuristically fresh" without asking the
server.  After a deploy, returning visitors therefore kept running the *old*
JavaScript and CSS against the new pages until their caches happened to refresh
— the cart, share sheet or menu then misbehaved "only sometimes".

``asset_url`` appends a short content hash (``?v=…``) so every changed file gets
a new URL: the browser cache and the service worker miss, and the fresh file is
fetched on the very first page view.  Unchanged files keep their URL and stay
cached.  Servers ignore the query string, so no web-server change is needed.
"""
import hashlib
import os
from functools import lru_cache

from django.conf import settings
from django.contrib.staticfiles import finders
from django.templatetags.static import static

_locations = {}


@lru_cache(maxsize=1024)
def _digest(location, mtime_ns, size):
    digest = hashlib.md5(usedforsecurity=False)
    with open(location, 'rb') as handle:
        for chunk in iter(lambda: handle.read(65536), b''):
            digest.update(chunk)
    return digest.hexdigest()[:10]


def _locate(path):
    location = _locations.get(path)
    if location:
        return location
    location = finders.find(path)
    if isinstance(location, (list, tuple)):
        location = location[0] if location else None
    if not location and settings.STATIC_ROOT:
        candidate = os.path.join(settings.STATIC_ROOT, path)
        location = candidate if os.path.isfile(candidate) else None
    if location:
        # Only hits are remembered: a file added later is still found.
        _locations[path] = location
    return location


def asset_version(path):
    """Short content hash of a static file, or '' when it cannot be read."""
    location = _locate(path)
    if not location:
        return ''
    try:
        stat = os.stat(location)
        # mtime + size in the key: an edited file is re-hashed, an unchanged one never is.
        return _digest(location, stat.st_mtime_ns, stat.st_size)
    except OSError:
        return ''


def asset_url(path):
    """``{% static path %}`` plus ``?v=<content hash>``."""
    url = static(path)
    version = asset_version(path)
    if not version:
        return url
    return f"{url}{'&' if '?' in url else '?'}v={version}"
