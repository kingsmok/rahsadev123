"""Storage backends for files that must never have a public media URL."""
import os

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible


@deconstructible
class PrivateDigitalStorage(FileSystemStorage):
    """Store paid assets outside ``MEDIA_ROOT`` with a read-only legacy fallback.

    The fallback lets an existing deployment switch its model field safely before
    ``migrate_private_digital_assets --apply`` copies old files. New uploads are
    always written below ``PRIVATE_MEDIA_ROOT`` and have no public URL.
    """

    def __init__(self):
        # Keep the setting dynamic so Django tests and deployment settings can
        # override PRIVATE_MEDIA_ROOT without recreating model field instances.
        super().__init__(location=None, base_url=None)

    @property
    def base_location(self):
        return os.path.abspath(settings.PRIVATE_MEDIA_ROOT)

    @property
    def location(self):
        return self.base_location

    def _legacy_path(self, name):
        return os.path.join(settings.MEDIA_ROOT, name)

    def path(self, name):
        private_path = super().path(name)
        if os.path.exists(private_path):
            return private_path
        legacy_path = self._legacy_path(name)
        if os.path.exists(legacy_path):
            return legacy_path
        return private_path

    def exists(self, name):
        return super().exists(name) or os.path.exists(self._legacy_path(name))
