"""خرید مهمان (بدون ثبت‌نام): سبد خرید نشست، دسترسی امن به سفارش و انتقال به حساب.

Rules
-----
* A guest cart is an ordinary :class:`~cart.models.Cart` without a user.  Only
  its primary key is kept in the *server-side* session, so a visitor can never
  point their session at somebody else's cart.
* A guest order is reachable from the browser session that placed it, or from
  the secret ``Order.access_token`` link (shown after payment, e-mailed, and
  re-sent by the order-tracking page).  The order number alone never grants
  access.
* A guest order moves into an account only with proof that the account holder
  placed it: the same browser session *and* a contact (mobile/e-mail) that
  matches the account on login, a verified one-time code, or a brand-new account
  created from that order's confirmation page.  Nothing is ever attached on the
  strength of a typed phone number or e-mail address alone.
"""
import logging

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from .coupons import release_coupon_reservation, revalidate_coupon
from .models import Cart, CartItem, Order

logger = logging.getLogger(__name__)

SESSION_CART_KEY = 'guest_cart_id'
SESSION_ORDERS_KEY = 'guest_orders'
SESSION_DETAILS_KEY = 'checkout_details'
SESSION_ERRORS_KEY = 'checkout_errors'
#: ``{order_pk: password_hash}`` — only when SMS codes are unavailable and the
#: buyer chose a password for the optional account.  The hash (never the
#: password) lives in the server-side session until the order is paid.
SESSION_ACCOUNT_KEY = 'checkout_account'
#: Orders for which the account-verification code was already sent automatically.
SESSION_OTP_SENT_KEY = 'checkout_account_otp'
MAX_SESSION_ORDERS = 20


# --------------------------------------------------------------------------- cart

def get_cart(request, create=False):
    """The visitor's cart: the account cart when signed in, else the session's guest cart."""
    user = getattr(request, 'user', None)
    if user is not None and user.is_authenticated:
        if create:
            cart, _ = Cart.objects.get_or_create(user=user)
            return cart
        return Cart.objects.filter(user=user).select_related('coupon').first()

    session = getattr(request, 'session', None)
    if session is None:
        return None
    cart = None
    cart_id = session.get(SESSION_CART_KEY)
    if cart_id:
        cart = Cart.objects.filter(pk=cart_id, user__isnull=True).select_related('coupon').first()
        if cart is None:
            # Paid (deleted), merged into an account, or cleaned up.
            session.pop(SESSION_CART_KEY, None)
    if cart is None and create:
        cart = Cart.objects.create()
        session[SESSION_CART_KEY] = cart.pk
    return cart


def merge_guest_cart(request, user):
    """Move the session's guest cart into ``user``'s cart (called on every login).

    Files already in the account cart are not duplicated.  The account cart's
    coupon wins; a coupon reserved by the guest cart is transferred when the
    account cart has none and released otherwise, so no reservation leaks.
    """
    session = getattr(request, 'session', None)
    if session is None:
        return None
    cart_id = session.pop(SESSION_CART_KEY, None)
    if not cart_id:
        return None
    with transaction.atomic():
        guest = Cart.objects.select_for_update().filter(pk=cart_id, user__isnull=True).first()
        if guest is None:
            return None
        target = Cart.objects.select_for_update().filter(user=user).first()
        if target is None:
            guest.user = user
            guest.save(update_fields=['user', 'updated_at'])
            target = guest
        else:
            owned = set(target.items.values_list('product_id', flat=True))
            CartItem.objects.filter(cart=guest).exclude(product_id__in=owned).update(cart=target)
            if guest.coupon_id and target.coupon_id is None:
                target.coupon_id, target.coupon_discount = guest.coupon_id, guest.coupon_discount
                target.save(update_fields=['coupon', 'coupon_discount', 'updated_at'])
            elif guest.coupon_id:
                release_coupon_reservation(guest.coupon)
            # A pending guest order keeps its immutable snapshot; pointing it at
            # the merged cart lets a later payment still remove what it bought.
            Order.objects.filter(cart=guest, status='pending').update(cart=target)
            guest.delete()
        # The discount is recomputed for the merged contents.
        revalidate_coupon(target, list(target.items.select_related('product')))
    return target


# ---------------------------------------------------------------- guest orders

def guest_order_ids(request):
    session = getattr(request, 'session', None)
    if session is None:
        return []
    return [pk for pk in (session.get(SESSION_ORDERS_KEY) or []) if isinstance(pk, int)]


def grant_order_access(request, order):
    """Let this browser session open ``order`` (a guest order) from now on."""
    if order.user_id is not None or getattr(request, 'session', None) is None:
        return
    ids = [pk for pk in guest_order_ids(request) if pk != order.pk]
    ids.append(order.pk)
    request.session[SESSION_ORDERS_KEY] = ids[-MAX_SESSION_ORDERS:]


def can_access_order(request, order):
    """Account orders: their owner only.  Guest orders: the session that placed or unlocked them."""
    if order.user_id is not None:
        user = getattr(request, 'user', None)
        return bool(user is not None and user.is_authenticated and user.pk == order.user_id)
    return order.pk in guest_order_ids(request)


def remember_checkout_details(request, mobile='', email='', create_account=False):
    """Keep what the buyer typed, so going back to edit the cart never loses it."""
    request.session[SESSION_DETAILS_KEY] = {
        'mobile': mobile or '',
        'email': email or '',
        'create_account': bool(create_account),
    }


def checkout_details(request):
    session = getattr(request, 'session', None)
    return dict(session.get(SESSION_DETAILS_KEY) or {}) if session is not None else {}


# ------------------------------------------------------------- account linking

def user_contacts(user):
    """Normalised mobile numbers and e-mail addresses recorded for an account."""
    from notifications.sms import normalize_mobile

    profile = getattr(user, 'profile', None)
    phones = {normalize_mobile(getattr(profile, 'phone', '') or '')} - {''}
    emails = {
        value.strip().lower()
        for value in (user.email, getattr(profile, 'email', '') or '')
        if value and value.strip()
    }
    return phones, emails


def attach_orders(user, order_ids):
    """Move guest orders (and their download tokens) into ``user``'s account.

    Callers must already have proven that the account holder placed them.  Only
    orders that are still guest orders are touched; returns their ids.
    """
    from downloads.models import DownloadToken

    order_ids = [pk for pk in order_ids if pk]
    if not order_ids:
        return []
    with transaction.atomic():
        ids = list(
            Order.objects.select_for_update()
            .filter(pk__in=order_ids, user__isnull=True)
            .values_list('pk', flat=True)
        )
        if ids:
            Order.objects.filter(pk__in=ids).update(user=user, updated_at=timezone.now())
            DownloadToken.objects.filter(order_id__in=ids, user__isnull=True).update(user=user)
    return ids


def attach_matching_session_orders(request, user):
    """On login: attach this session's guest orders whose contact matches the account.

    The session proves the visitor placed the order and the login proves they
    own the account; the contact match keeps a shared computer from handing one
    buyer's order to the next person who signs in on it.
    """
    ids = guest_order_ids(request)
    if not ids:
        return []
    phones, emails = user_contacts(user)
    if not phones and not emails:
        return []
    matching = [
        order.pk
        for order in Order.objects.filter(pk__in=ids, user__isnull=True).only('pk', 'contact_mobile', 'contact_email')
        if (order.contact_mobile and order.contact_mobile in phones)
        or (order.contact_email and order.contact_email.lower() in emails)
    ]
    return attach_orders(user, matching)


def contact_in_use(mobile, email):
    """Whether a new account with these details would collide with an existing account."""
    from accounts.models import Profile

    User = get_user_model()
    if mobile and (
        Profile.objects.filter(phone=mobile).exists()
        or User.objects.filter(username__iexact=mobile).exists()
    ):
        return True
    if email and (
        User.objects.filter(email__iexact=email).exists()
        or Profile.objects.filter(email__iexact=email).exists()
    ):
        return True
    return False


def create_account_from_order(order, password_hash):
    """Password mode: a new account from a paid guest order's details, or ``None``.

    Used only when SMS codes are unavailable, so neither contact is verified:
    the mobile becomes the username but is *not* stored as the profile phone
    (that phone would otherwise unlock the account through SMS login if it was
    mistyped), and an existing account is never touched.
    """
    User = get_user_model()
    mobile = order.contact_mobile
    email = (order.contact_email or '').strip().lower()
    if not mobile or not password_hash or contact_in_use(mobile, email):
        return None
    with transaction.atomic():
        user = User(username=mobile, email=email)
        user.password = password_hash
        user.save()
    return user


def account_for_verified_phone(phone, email=''):
    """SMS mode: the account owning a *verified* phone, created when there is none.

    Returns ``(user, created)``; raises :class:`accounts.otp.OtpError`.  A new
    account also receives the checkout e-mail unless another account uses it.
    """
    from accounts.otp import user_for_phone

    user, created = user_for_phone(phone)
    email = (email or '').strip().lower()
    if created and email:
        User = get_user_model()
        if not User.objects.filter(email__iexact=email).exclude(pk=user.pk).exists():
            user.email = email
            user.save(update_fields=['email'])
            profile = getattr(user, 'profile', None)
            if profile is not None and not profile.email:
                profile.email = email
                profile.save(update_fields=['email'])
    return user, created
