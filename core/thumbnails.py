"""HTML helpers for model methods shown in admin list columns.

Kept free of ``django.contrib.admin`` imports because model modules import it.
"""
from django.utils.html import format_html


def admin_thumbnail(image, alt, width=50, height=50):
    """Thumbnail for an admin list column (shared by every model with an image).

    Replaces five copies of ``<img width="50px" height="50px">``: they had no
    alt text, used length units the HTML attributes do not accept, and
    stretched non-square images into the box.  The "no image" marker was an
    ``<h3>`` inside a table cell, i.e. one fake heading per row for screen
    readers navigating by headings.
    """
    if not image:
        return format_html('<span style="color: var(--error-fg, #ba2121)">{}</span>', 'تصویر ندارد')
    return format_html(
        '<img src="{}" alt="{}" width="{}" height="{}" loading="lazy" decoding="async" '
        'style="object-fit: cover; border-radius: 6px; vertical-align: middle">',
        image.url, alt, width, height,
    )
