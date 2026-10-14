"""Shared validators for user-submitted uploads.

Staff uploads through the admin are trusted, but anything a registered customer
can post should be bounded.  There is no framework default that caps how large a
still-valid image may be, so an unbounded upload is a cheap way to exhaust the
disk - which matters on the shared-hosting deployment this project documents.
"""
from __future__ import annotations

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

# 5 MB is generous for an avatar or product photo, and small enough that the
# image-optimisation pipeline can hold it in memory without strain.
MAX_IMAGE_UPLOAD_BYTES = 5 * 1024 * 1024


def human_readable_size(num_bytes: int) -> str:
    """Render a byte count using the site's Persian locale conventions."""
    value = float(num_bytes)
    for unit in ('بایت', 'کیلوبایت', 'مگابایت'):
        if value < 1024 or unit == 'مگابایت':
            return f'{value:.0f} {unit}' if value == int(value) else f'{value:.1f} {unit}'
        value /= 1024
    return f'{value:.1f} مگابایت'


def validate_image_size(value) -> None:
    """Reject images larger than :data:`MAX_IMAGE_UPLOAD_BYTES`.

    ImageField already proves the file *is* an image; this bounds how big it can
    be.  ``value`` is an ``UploadedFile``, so ``size`` is already known.
    """
    size = getattr(value, 'size', None)
    if size is None:
        return
    if size > MAX_IMAGE_UPLOAD_BYTES:
        raise ValidationError(
            _('حجم تصویر %(actual)s است؛ حداکثر %(limit)s مجاز است.'),
            code='image_too_large',
            params={
                'actual': human_readable_size(size),
                'limit': human_readable_size(MAX_IMAGE_UPLOAD_BYTES),
            },
        )
