"""Coupon rules shared by the cart, the payment page and checkout start.

Kept in one module so the cart page, the payment page and
``payments.views.start_payment`` cannot disagree about whether a discount
still applies.
"""
from django.db.models import F
from django.utils import timezone

from .models import Coupon


def discount_amount(coupon, total_price):
    """مبلغ تخفیف یک کوپن برای یک جمع مشخص (هرگز منفی یا بیش از جمع سبد)."""
    if coupon.discount_type == 'percentage':
        discount = int((total_price * coupon.discount_value) / 100)
    else:
        discount = coupon.discount_value
    if coupon.maximum_discount:
        discount = min(discount, coupon.maximum_discount)
    return max(0, min(discount, total_price))


def release_coupon_reservation(coupon):
    """Give back the global use reserved for a coupon that is being detached.

    ``apply_coupon`` reserves one of the coupon's global uses so that two carts
    cannot both claim the last one.  If that reservation is dropped without a
    payment (cart emptied, coupon removed, or it stopped qualifying), the use
    must be returned — otherwise anyone could burn a campaign's whole budget by
    repeatedly applying and dropping the same code.

    ``is_active`` is intentionally left alone: it is staff's switch, and a
    coupon is never deactivated automatically when its capacity fills up.
    """
    if coupon is None:
        return
    Coupon.objects.filter(pk=coupon.pk, usage_count__gt=0).update(
        usage_count=F('usage_count') - 1
    )


def revalidate_coupon(cart, items):
    """Recompute the applied coupon against the cart's *current* contents.

    A discount is calculated from the cart total at the time it is applied.  If
    the customer then removes the expensive item that justified it, the stale
    amount must not survive: left untouched, a 500,000 discount on a 100,000
    cart makes the order payable for zero.  Re-run the same rules here and drop
    the coupon when it no longer qualifies (expired, disabled by staff, below
    the minimum order amount).

    Capacity (``max_usage``) is deliberately *not* re-checked: this cart's own
    reservation is already part of ``usage_count``.

    Returns ``True`` when the stored coupon or discount had to change.
    """
    if cart is None or cart.coupon is None:
        return False

    coupon = cart.coupon
    total_price = sum(item.total_price for item in items)
    now = timezone.now()

    still_valid = (
        bool(items)
        and coupon.is_active
        and coupon.valid_from <= now <= coupon.valid_to
        and (not coupon.minimum_order_amount or total_price >= coupon.minimum_order_amount)
    )

    if still_valid:
        new_coupon, new_discount = coupon, discount_amount(coupon, total_price)
    else:
        new_coupon, new_discount = None, 0

    # ``cart`` is revalidated on every page view, so only touch the database
    # when the stored values really are stale.
    if cart.coupon_id == (new_coupon.pk if new_coupon else None) \
            and cart.coupon_discount == new_discount:
        return False

    if new_coupon is None:
        # The reservation is dropped without a payment, so return the use.
        release_coupon_reservation(coupon)

    cart.coupon = new_coupon
    cart.coupon_discount = new_discount
    cart.save(update_fields=['coupon', 'coupon_discount', 'updated_at'])
    return True
