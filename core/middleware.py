# -*- coding: utf-8 -*-
"""میدل‌ور ریدایرکت — هدایت خودکار آدرس‌های قدیمی بر اساس تنظیمات پنل.

قبل از پردازش درخواست، مسیر در جدول ریدایرکت‌ها جست‌وجو می‌شود؛
در صورت وجود، با کد ۳۰۱ (دائمی) یا ۳۰۲ (موقت) هدایت انجام می‌شود.
"""
from django.db.models import F
from django.http import HttpResponseRedirect, HttpResponsePermanentRedirect

from core.models import Redirect


class RedirectMiddleware:
    """ریدایرکت آدرس‌های ثبت‌شده در پنل مدیریت."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # فقط متدهای امن؛ برای فایل‌های استاتیک/مدیا هزینه ندهیم
        if request.method in ('GET', 'HEAD'):
            redirect_obj = self._find_redirect(request.path)
            if redirect_obj is not None:
                # شمارش دفعات استفاده (بدون race condition با F)
                Redirect.objects.filter(pk=redirect_obj.pk).update(hits=F('hits') + 1)
                if redirect_obj.status_code == '302':
                    return HttpResponseRedirect(redirect_obj.new_path)
                return HttpResponsePermanentRedirect(redirect_obj.new_path)
        return self.get_response(request)

    @staticmethod
    def _find_redirect(path):
        """جست‌وجوی ریدایرکت فعال برای مسیر — با و بدون اسلش انتهایی."""
        if path in ('/', ''):
            return None
        candidates = [path]
        if path.endswith('/'):
            stripped = path.rstrip('/')
            if stripped:
                candidates.append(stripped)
        else:
            candidates.append(path + '/')
        try:
            return (
                Redirect.objects
                .filter(old_path__in=candidates, is_active=True)
                .exclude(new_path__in=candidates)  # جلوگیری از حلقه ریدایرکت
                .first()
            )
        except Exception:
            # اگر جدول هنوز ساخته نشده بود (اولین راه‌اندازی) مزاحم نیستیم
            return None
