from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
    verbose_name = 'اپ اصلی'

    def ready(self):
        # پچ‌های سازگاری با پایتون ۳.۱۴ (خطای 'super' object has no attribute 'dicts')
        from MasaiShop.compat import apply_patches

        apply_patches()
