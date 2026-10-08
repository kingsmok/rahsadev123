"""Safe, lossless-metadata image optimisation for Django uploads.

The helper is deliberately conservative: it processes only single-frame JPEG,
PNG and WebP uploads. GIFs (which may be animated) and unknown formats are
left untouched instead of risking broken uploaded content.
"""
from __future__ import annotations

from io import BytesIO
import logging
from pathlib import PurePath

from django.conf import settings
from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError

logger = logging.getLogger(__name__)

_SUPPORTED_FORMATS = {'JPEG', 'PNG', 'WEBP'}


def _setting(name, default):
    return getattr(settings, name, default)


def optimise_uploaded_image(uploaded_file):
    """Return an optimised WebP ``ContentFile`` or ``None`` when skipped.

    Uploaded files are resized only when either dimension is above the configured
    limit. Re-encoding removes camera metadata such as EXIF GPS coordinates. If
    WebP would make an already-small image larger, the original is retained.
    """
    if not _setting('IMAGE_OPTIMIZATION_ENABLED', True):
        return None

    source = getattr(uploaded_file, 'file', uploaded_file)
    if source is None or not hasattr(source, 'read'):
        return None

    try:
        if hasattr(source, 'seek'):
            source.seek(0)
        original_bytes = source.read()
        if not original_bytes:
            return None

        with Image.open(BytesIO(original_bytes)) as opened:
            image_format = (opened.format or '').upper()
            if image_format not in _SUPPORTED_FORMATS or getattr(opened, 'is_animated', False):
                return None

            # Respect EXIF orientation before calculating output dimensions.
            image = ImageOps.exif_transpose(opened)
            image.load()
            max_dimension = max(1, int(_setting('IMAGE_OPTIMIZATION_MAX_DIMENSION', 2000)))
            original_size = image.size
            if max(image.size) > max_dimension:
                image.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)

            # WebP accepts RGB/RGBA. Converting also strips EXIF and other
            # non-essential metadata when Pillow writes the new asset.
            if image.mode in ('RGBA', 'LA') or (image.mode == 'P' and 'transparency' in image.info):
                image = image.convert('RGBA')
            elif image.mode != 'RGB':
                image = image.convert('RGB')

            output = BytesIO()
            image.save(
                output,
                format='WEBP',
                quality=max(1, min(100, int(_setting('IMAGE_OPTIMIZATION_WEBP_QUALITY', 82)))),
                method=6,
            )

        optimized_bytes = output.getvalue()
        # Keep the source if recompressing would waste bytes and did not resize.
        if len(optimized_bytes) >= len(original_bytes) and image.size == original_size:
            return None

        original_name = PurePath(getattr(uploaded_file, 'name', 'image')).name
        stem = PurePath(original_name).stem or 'image'
        return ContentFile(optimized_bytes, name=f'{stem}.webp')
    except (OSError, UnidentifiedImageError, ValueError) as exc:
        # ImageField validation remains the authority for accepting/rejecting an
        # upload. Optimisation must never make a valid upload unavailable.
        logger.warning('Skipping image optimisation for %s: %s', getattr(uploaded_file, 'name', 'upload'), exc)
        return None
    finally:
        if hasattr(source, 'seek'):
            try:
                source.seek(0)
            except OSError:
                pass
