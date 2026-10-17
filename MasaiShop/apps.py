from django.contrib.admin.apps import AdminConfig


class FileMarketAdminConfig(AdminConfig):
    """``django.contrib.admin`` با سایت ادمینی که نام برند را از تنظیمات سایت می‌خواند."""

    default_site = 'MasaiShop.admin_branding.FileMarketAdminSite'
