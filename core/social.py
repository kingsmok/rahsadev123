"""شبکه‌های اجتماعی خارجی و ایرانی که در فوتر، صفحهٔ تماس و منوی موبایل نمایش داده می‌شوند.

آیکن‌ها در ``static/img/social/social-sprite.svg`` هستند (``#si-<key>``).
قبلاً لینک‌ها با کلاس ``fa fa-instagram`` رندر می‌شدند؛ در Font Awesome 6 آیکن
برندها فقط با ``fa-brands`` و فونت brands دیده می‌شوند و ``fa-x-twitter`` اصلاً در
نسخهٔ 6.4.0 پروژه وجود ندارد — نتیجه لینک‌هایی بدون هیچ آیکن قابل مشاهده بود.
"""
import re
from urllib.parse import urlsplit

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator

_SCHEME = re.compile(r'^[a-zA-Z][a-zA-Z0-9+.-]*:')
_validate_url = URLValidator(schemes=['http', 'https'])

# key, SiteSettings field, label, group, brand colour, base URL for "@handle" values
NETWORKS = (
    ('instagram', 'instagram_link', 'اینستاگرام', 'global', '#E1306C', 'https://instagram.com/'),
    ('telegram', 'telegram_link', 'تلگرام', 'global', '#229ED9', 'https://t.me/'),
    ('whatsapp', 'whatsapp_link', 'واتساپ', 'global', '#25D366', ''),
    ('x', 'twitter_link', 'ایکس (توییتر)', 'global', '#111111', 'https://x.com/'),
    ('youtube', 'youtube_link', 'یوتیوب', 'global', '#FF0000', 'https://youtube.com/@'),
    ('linkedin', 'linkedin_link', 'لینکدین', 'global', '#0A66C2', ''),
    ('facebook', 'facebook_link', 'فیسبوک', 'global', '#1877F2', 'https://facebook.com/'),
    ('pinterest', 'pinterest_link', 'پینترست', 'global', '#E60023', 'https://pinterest.com/'),
    ('github', 'github_link', 'گیت‌هاب', 'global', '#24292F', 'https://github.com/'),
    ('aparat', 'aparat_link', 'آپارات', 'iran', '#ED145B', 'https://www.aparat.com/'),
    ('eitaa', 'eitaa_link', 'ایتا', 'iran', '#F27522', 'https://eitaa.com/'),
    ('rubika', 'rubika_link', 'روبیکا', 'iran', '#7B2FF7', 'https://rubika.ir/'),
    ('bale', 'bale_link', 'بله', 'iran', '#00A884', 'https://ble.ir/'),
    ('soroush', 'soroush_link', 'سروش پلاس', 'iran', '#2D7FF9', 'https://splus.ir/'),
    ('igap', 'igap_link', 'آی‌گپ', 'iran', '#00A3E0', 'https://igap.net/'),
    ('virgool', 'virgool_link', 'ویرگول', 'iran', '#3341A6', 'https://virgool.io/@'),
)

# مقادیر نمونه‌ای که قبلاً پیش‌فرض مدل بودند؛ لینک واقعی نیستند.
PLACEHOLDERS = {
    'https://instagram.com/username',
    'https://www.instagram.com/username',
    'https://t.me/username',
}


def normalise_link(value, handle_base=''):
    value = (value or '').strip()
    if not value or value in PLACEHOLDERS or value.rstrip('/') in PLACEHOLDERS:
        return ''
    if value.startswith('@') and handle_base:
        handle = value[1:].strip()
        return handle_base + handle if handle and '/' not in handle else ''
    if value.startswith('//'):
        value = 'https:' + value
    elif _SCHEME.match(value) and not value.lower().startswith(('http://', 'https://')):
        return ''  # javascript:, data:, tel: … are never rendered as social links
    elif '://' not in value:
        value = 'https://' + value.lstrip('/')
    parts = urlsplit(value)
    if parts.scheme not in ('http', 'https') or not parts.netloc:
        return ''
    try:
        _validate_url(value)
    except ValidationError:
        return ''
    return value


def social_links(site_settings):
    """Configured networks as dicts: key, label, url, group, color."""
    links = []
    if site_settings is None:
        return links
    for key, field, label, group, color, handle_base in NETWORKS:
        url = normalise_link(getattr(site_settings, field, '') or '', handle_base)
        if url:
            links.append({'key': key, 'label': label, 'url': url, 'group': group, 'color': color})
    return links
