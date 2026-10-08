"""برندینگ سراسری Django Admin فایل‌مارکت.

عنوان‌های ادمین در یک نقطه تنظیم می‌شوند تا در سربرگ مرورگر، صفحهٔ ورود و
هدر همهٔ صفحه‌ها یکسان باشند.
"""
from django.contrib import admin

SITE_HEADER = 'مدیریت فایل‌مارکت'
SITE_TITLE = 'مدیریت فایل‌مارکت'
INDEX_TITLE = 'خانهٔ مدیریت'


def configure_admin_site():
    """عنوان‌های ادمین را اعمال می‌کند (از MasaiShop.urls صدا زده می‌شود)."""
    admin.site.site_header = SITE_HEADER
    admin.site.site_title = SITE_TITLE
    admin.site.index_title = INDEX_TITLE
    admin.site.enable_nav_sidebar = True
