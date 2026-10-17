"""ورود به حساب، سبد و سفارش‌های مهمانِ همان مرورگر را به حساب منتقل می‌کند."""
import logging

from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver

from .guest import attach_matching_session_orders, merge_guest_cart

logger = logging.getLogger(__name__)


@receiver(user_logged_in, dispatch_uid='cart_guest_session_to_account')
def guest_session_to_account(sender, request, user, **kwargs):
    """Every login path (password, SMS code, checkout account, admin) ends here.

    Never raises: a problem while merging must not block the login itself.
    """
    if request is None or getattr(request, 'session', None) is None:
        return
    try:
        merge_guest_cart(request, user)
        attach_matching_session_orders(request, user)
    except Exception:
        logger.exception('انتقال سبد/سفارش مهمان به حساب %s انجام نشد.', user.pk)
