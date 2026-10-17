"""The shop's brand identity — name, logo and browser icons — in one place.

Before this module the name «فایل‌مارکت» and the old heart icon were repeated
in templates and static files: the Django admin header and title, the staff
panel, the offline page, the PWA manifest, the hero slider and
``/favicon.ico`` (a *permanent* redirect, so browsers never asked again).
Renaming the shop or uploading a new logo in «تنظیمات سایت» therefore only
changed the storefront header, and the tab icon could not be changed at all.

Every surface now reads the brand through :func:`get_brand`, which looks the
settings row up once per request.  Nothing is cached across requests on
purpose: with the default per-process LocMem cache a signal-based
invalidation would only reach the worker that handled the save, and the
other workers would keep showing the old name.
"""
import hashlib
import re
from io import BytesIO

from django.db import OperationalError, ProgrammingError
from django.templatetags.static import static
from django.urls import reverse
from django.utils.functional import cached_property
from PIL import Image, ImageOps

DEFAULT_SITE_NAME = 'فایل‌مارکت'
DEFAULT_DESCRIPTION = (
    'خرید و دانلود آنی فایل‌های نرم‌افزاری، قالب وب سایت، اسکریپت و محصولات مجازی با لایسنس رسمی'
)

#: Square icon sizes the icon endpoint renders (anything else is a 404, so the
#: endpoint cannot be used to make the server resize images to arbitrary sizes).
#: 32 → tab favicon, 180 → apple-touch-icon / admin mark, 192 & 512 → PWA.
ICON_SIZES = (32, 180, 192, 512)

#: Bundled icons used until a favicon or logo is uploaded.
DEFAULT_ICONS = {
    32: 'img/favicon.png',
    180: 'img/favicon.png',
    192: 'img/pwa/icon-192.png',
    512: 'img/pwa/icon-512.png',
}
DEFAULT_FAVICON_ICO = 'favicon.ico'

#: Errors that mean "this uploaded file cannot be turned into an icon right
#: now" (missing on disk, unreadable, not an image, absurdly large).
ICON_ERRORS = (OSError, ValueError, SyntaxError, Image.DecompressionBombError)

#: Text fields of ``SiteSettings`` that normally repeat the shop's name.
NAME_BEARING_FIELDS = (
    'site_slogan', 'default_meta_title', 'default_meta_description',
    'footer_description', 'copy_right', 'text_about_us', 'text_contact_us',
)

_UNSET = object()


def get_site_settings(request=None):
    """Return the active ``SiteSettings`` row (the first by pk) or ``None``.

    The lookup is memoised on ``request`` so the context processor, the admin
    site and template tags share a single query.  A database that is not
    migrated yet (e.g. new code deployed just before ``migrate``) yields
    ``None`` — the default brand — instead of a 500 on every page.
    """
    if request is not None:
        cached = getattr(request, '_fm_site_settings', _UNSET)
        if cached is not _UNSET:
            return cached
    from core.models import SiteSettings

    try:
        settings_obj = SiteSettings.objects.order_by('pk').first()
    except (OperationalError, ProgrammingError):
        settings_obj = None
    if request is not None:
        request._fm_site_settings = settings_obj
    return settings_obj


def get_brand(request=None):
    """The :class:`Brand` for this request (memoised alongside the settings)."""
    if request is not None:
        cached = getattr(request, '_fm_brand', None)
        if cached is not None:
            return cached
    brand = Brand(get_site_settings(request))
    if request is not None:
        request._fm_brand = brand
    return brand


def brand_initial(name):
    """First letter of the name for the text logo («فایل‌مارکت» → «ف»)."""
    for char in name or '':
        if char.isalnum():
            return char.upper()
    stripped = (name or '').strip()
    return stripped[:1] or DEFAULT_SITE_NAME[:1]


def _with_version(url, version):
    return f'{url}{"&" if "?" in url else "?"}v={version}'


def _stored_file(settings_obj, field_name):
    field_file = getattr(settings_obj, field_name, None) if settings_obj is not None else None
    return field_file if field_file and getattr(field_file, 'name', '') else None


class Brand:
    """Template-friendly, never-raising view of the shop's identity."""

    def __init__(self, settings_obj=None):
        self.settings = settings_obj
        self.name = (getattr(settings_obj, 'site_name', '') or '').strip() or DEFAULT_SITE_NAME
        self.slogan = (getattr(settings_obj, 'site_slogan', '') or '').strip()

    @cached_property
    def version(self):
        """Short token that changes whenever the settings (or their files) change.

        It is appended to every brand asset URL.  Without it a re-uploaded logo
        can get the very same file name (django-cleanup deletes the previous
        file) and browsers keep showing the cached old image.
        """
        settings_obj = self.settings
        if settings_obj is None:
            return 'default'
        stamp = getattr(settings_obj, 'updated_at', None)
        basis = '|'.join((
            str(settings_obj.pk),
            stamp.isoformat() if stamp else '',
            getattr(_stored_file(settings_obj, 'logo'), 'name', ''),
            getattr(_stored_file(settings_obj, 'logo_dark'), 'name', ''),
            getattr(_stored_file(settings_obj, 'favicon'), 'name', ''),
            self.name,
        ))
        return hashlib.sha256(basis.encode('utf-8')).hexdigest()[:12]

    @cached_property
    def initial(self):
        return brand_initial(self.name)

    @property
    def admin_title(self):
        return f'مدیریت {self.name}'

    @cached_property
    def logo_url(self):
        logo = _stored_file(self.settings, 'logo')
        return _with_version(logo.url, self.version) if logo else ''

    @cached_property
    def logo_dark_url(self):
        """Light-on-dark variant shown in dark mode; only meaningful with a main logo."""
        logo = _stored_file(self.settings, 'logo_dark')
        return _with_version(logo.url, self.version) if logo and self.logo_url else ''

    @cached_property
    def icon_source(self):
        """The uploaded image every icon is rendered from: favicon, else logo."""
        return _stored_file(self.settings, 'favicon') or _stored_file(self.settings, 'logo')

    @property
    def has_custom_icon(self):
        return self.icon_source is not None

    @property
    def has_favicon(self):
        """A dedicated (square) favicon was uploaded, not just a logo."""
        return _stored_file(self.settings, 'favicon') is not None

    def icon_url(self, size):
        if self.has_custom_icon:
            return _with_version(reverse('core:brand_icon', args=[size]), self.version)
        return static(DEFAULT_ICONS[size])

    @property
    def favicon_url(self):
        return self.icon_url(32)

    @property
    def touch_icon_url(self):
        return self.icon_url(180)

    @property
    def icon_192_url(self):
        return self.icon_url(192)

    @property
    def icon_512_url(self):
        return self.icon_url(512)

    @property
    def favicon_ico_url(self):
        """Target of the conventional ``/favicon.ico`` probe."""
        return self.favicon_url if self.has_custom_icon else static(DEFAULT_FAVICON_ICO)

    @property
    def manifest_url(self):
        return _with_version(reverse('core:web_manifest'), self.version)


def render_square_icon(field_file, size):
    """Render ``field_file`` as a ``size``×``size`` PNG with a transparent margin.

    The whole image is scaled to fit (never cropped, never stretched), so a
    wide logo becomes a centred strip instead of a squashed blob; small
    sources are scaled up to fill the square.
    """
    with field_file.open('rb') as handle:
        with Image.open(handle) as source:
            source.draft('RGB', (size, size))  # cheap JPEG down-scaling; no-op otherwise
            image = ImageOps.exif_transpose(source).convert('RGBA')
    scale = size / max(image.size)
    fitted = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
    if fitted != image.size:
        image = image.resize(fitted, Image.Resampling.LANCZOS)
    canvas = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    canvas.alpha_composite(image, ((size - fitted[0]) // 2, (size - fitted[1]) // 2))
    output = BytesIO()
    canvas.save(output, format='PNG', optimize=True)
    return output.getvalue()


def manifest_data(brand):
    """Web app manifest built from the current brand (was a static JSON file)."""
    settings_obj = brand.settings
    description = (getattr(settings_obj, 'default_meta_description', '') or '').strip() or DEFAULT_DESCRIPTION
    if brand.has_custom_icon:
        icons = [
            {'src': brand.icon_192_url, 'sizes': '192x192', 'type': 'image/png', 'purpose': 'any'},
            {'src': brand.icon_512_url, 'sizes': '512x512', 'type': 'image/png', 'purpose': 'any'},
        ]
    else:
        icons = [
            {'src': brand.icon_192_url, 'sizes': '192x192', 'type': 'image/png', 'purpose': 'any maskable'},
            {'src': brand.icon_512_url, 'sizes': '512x512', 'type': 'image/png', 'purpose': 'any maskable'},
        ]
    shortcut_icons = [{'src': brand.icon_192_url, 'sizes': '192x192', 'type': 'image/png'}]
    return {
        'id': '/',
        'name': f'{brand.name} | {brand.slogan}' if brand.slogan else brand.name,
        'short_name': brand.name,
        'description': description,
        'lang': 'fa-IR',
        'dir': 'rtl',
        'start_url': '/?source=pwa',
        'scope': '/',
        'display': 'standalone',
        'display_override': ['window-controls-overlay', 'standalone', 'browser'],
        'orientation': 'any',
        'background_color': '#f6f8fa',
        'theme_color': '#46a9ae',
        'icons': icons,
        'shortcuts': [
            {
                'name': 'همه فایل‌ها',
                'short_name': 'فایل‌ها',
                'url': reverse('product:product_list') + '?source=pwa-shortcut',
                'icons': shortcut_icons,
            },
            {
                'name': 'تخفیف‌های ویژه',
                'short_name': 'تخفیف‌ها',
                'url': reverse('product:discount_product') + '?source=pwa-shortcut',
                'icons': shortcut_icons,
            },
            {
                'name': 'دانلودهای من',
                'short_name': 'دانلودها',
                'url': reverse('dashboard:my_downloads') + '?source=pwa-shortcut',
                'icons': shortcut_icons,
            },
        ],
    }


def replace_name(text, old, new):
    """Replace whole-word occurrences of the old shop name in ``text``.

    Persian suffixes joined with a ZWNJ («فایل‌مارکت‌ها») still match, while a
    name that is only part of a longer word does not.  When the new name
    contains the old one («فایل‌مارکت» → «فایل‌مارکت پلاس»), occurrences that
    are already the new name are left alone instead of becoming
    «فایل‌مارکت پلاس پلاس».
    """
    if not text or not old or old == new or old not in text:
        return text
    pattern = re.compile(r'(?<!\w)%s(?!\w)' % re.escape(old))
    if new and old in new:
        return new.join(pattern.sub(new, part) for part in text.split(new))
    return pattern.sub(new, text)
