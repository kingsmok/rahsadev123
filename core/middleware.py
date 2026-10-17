# -*- coding: utf-8 -*-
"""میدل‌ور ریدایرکت — هدایت خودکار آدرس‌های قدیمی بر اساس تنظیمات پنل.

قبل از پردازش درخواست، مسیر در جدول ریدایرکت‌ها جست‌وجو می‌شود؛
در صورت وجود، با کد ۳۰۱ (دائمی) یا ۳۰۲ (موقت) هدایت انجام می‌شود.
"""
from django.db import OperationalError, ProgrammingError
from django.db.models import F
from django.http import HttpResponseRedirect, HttpResponsePermanentRedirect

from core.models import Redirect


class BrowserPolicyMiddleware:
    """Apply a small, compatibility-safe browser feature policy everywhere.

    The storefront does not use sensors, device hardware, or the Payment
    Request API (payments are redirected to a gateway), so disabling them
    reduces attack surface without changing checkout behavior.

    The Content-Security-Policy is deliberately scoped to how this project
    actually renders pages: templates rely on inline scripts/styles and
    same-origin static assets (no third-party script/style origins exist),
    so external script execution, plugins, base-tag hijacking and framing
    can be denied without breaking the storefront. ``img-src`` keeps
    ``https:`` because staff-authored rich text may legitimately embed
    externally hosted images; images cannot execute script. Views may
    still override the header when a page demonstrably needs more.
    """

    _POLICY = 'camera=(), geolocation=(), microphone=(), payment=(), usb=()'
    _CSP_TEMPLATE = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob: https:; "
        "font-src 'self' data:; "
        "media-src 'self'; "
        "connect-src 'self'; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "form-action {form_action}; "
        "frame-ancestors 'none'; "
        "worker-src 'self'"
    )

    def __init__(self, get_response):
        self.get_response = get_response
        # ``form-action`` also governs the redirects that follow a form POST.
        # Checkout POSTs to ``payments:start``, which 302s to the gateway, so
        # a bare ``'self'`` made the browser block every payment.  Imported
        # here (apps are ready once middleware is built) to keep the gateway
        # list in one place.
        from payments.gateways import CHECKOUT_REDIRECT_ORIGINS

        self.csp = self._CSP_TEMPLATE.format(
            form_action=' '.join(("'self'", *CHECKOUT_REDIRECT_ORIGINS)),
        )

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault('Permissions-Policy', self._POLICY)
        response.setdefault('Content-Security-Policy', self.csp)
        return response


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
        except (OperationalError, ProgrammingError):
            # Only a missing/outdated table is tolerated (first boot, before
            # migrations).  Any other error must surface instead of silently
            # disabling every redirect.
            return None
