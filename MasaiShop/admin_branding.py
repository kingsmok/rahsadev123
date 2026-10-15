"""برندینگ سراسری Django Admin.

سربرگ ادمین و عنوان تب مرورگر در همهٔ صفحه‌های ادمین (از جمله صفحهٔ ورود)
از «تنظیمات سایت» خوانده می‌شوند (``core.branding``). پیش از این رشتهٔ ثابت
«مدیریت فایل‌مارکت» یک بار هنگام بارگذاری urls روی ``admin.site`` نوشته می‌شد
و پس از تغییر نام سایت هم در ادمین باقی می‌ماند.

این کلاس از طریق ``MasaiShop.apps.FileMarketAdminConfig`` (در INSTALLED_APPS)
سایت پیش‌فرض ادمین می‌شود؛ همهٔ ``admin.site.register``ها بدون تغییر کار می‌کنند.
"""
from django.contrib import admin

from core.branding import DEFAULT_SITE_NAME, get_brand

INDEX_TITLE = 'خانهٔ مدیریت'


class FileMarketAdminSite(admin.AdminSite):
    # فقط مقدار پیش‌فرض؛ مقدار واقعی در each_context از تنظیمات سایت می‌آید.
    site_header = f'مدیریت {DEFAULT_SITE_NAME}'
    site_title = f'مدیریت {DEFAULT_SITE_NAME}'
    index_title = INDEX_TITLE
    enable_nav_sidebar = True

    def each_context(self, request):
        context = super().each_context(request)
        # Same per-request lookup as the context processor: no extra query.
        title = get_brand(request).admin_title
        context['site_header'] = title
        context['site_title'] = title
        return context
