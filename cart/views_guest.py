"""سفارش مهمان: صفحهٔ سفارش با لینک محرمانه، پیگیری سفارش و ساخت حساب اختیاری.

Privacy
-------
Nothing here tells a visitor whether some phone number or e-mail address has an
account.  The tracking page answers identically whether or not an order
matches, and an account is only created/opened after the visitor proves they
own the phone (one-time SMS code, the project's existing passwordless login)
— or, when SMS codes are unavailable, from the paid order's own confirmation
page with the password the buyer chose at checkout.
"""
import logging
import re

from django.contrib import messages
from django.contrib.auth import login
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from core.throttling import get_throttle

from .guest import (
    SESSION_ACCOUNT_KEY, SESSION_OTP_SENT_KEY, account_for_verified_phone, attach_orders, can_access_order,
    create_account_from_order, grant_order_access, guest_order_ids,
)
from .models import Order

logger = logging.getLogger(__name__)

_TRACK_SESSION_KEY = 'order_track_lookup'
_CONFLICT_SESSION_KEY = 'checkout_account_conflict'
_LOGIN_BACKEND = 'django.contrib.auth.backends.ModelBackend'
_GENERIC_CODE_ERROR = 'کد واردشده درست نیست یا منقضی شده است؛ در صورت نیاز کد جدید بگیرید.'


def _otp_available():
    from .views import _otp_available as available

    return available()


def order_path(order):
    return reverse('cart:guest_order', kwargs={'access_token': order.access_token})


def order_link(request, order):
    """Absolute secret link of a guest order (SITE_URL when configured)."""
    from notifications.services import absolute_url

    path = order_path(order)
    link = absolute_url(path)
    return link if link.startswith('http') else request.build_absolute_uri(path)


def _mask_email(email):
    if not email or '@' not in email:
        return ''
    name, domain = email.split('@', 1)
    return f'{name[:2]}***@{domain}'


def _session_orders_with_contact(request, mobile='', email=''):
    """This session's guest orders placed with the given (already trusted) contact."""
    email = (email or '').lower()
    return [
        order.pk
        for order in Order.objects.filter(pk__in=guest_order_ids(request), user__isnull=True)
        if (mobile and order.contact_mobile == mobile) or (email and order.contact_email.lower() == email)
    ]


def account_card_context(request, order, auto_send=False):
    """The optional «create an account» card on a paid guest order.

    With SMS codes available and the buyer having opted in at checkout, the
    code is sent automatically the first time the confirmation page opens
    (once per order and session); otherwise a button sends it on request.
    """
    if order.user_id or order.status not in Order.COMPLETED_STATUSES or not order.contact_mobile:
        return {'account_card': None}
    from accounts.otp import OtpError, issue_code, mask_phone, seconds_until_resend

    otp = _otp_available()
    card = {
        'mode': 'otp' if otp else 'password',
        'requested': order.create_account_requested,
        'mobile_masked': mask_phone(order.contact_mobile),
        'email_masked': _mask_email(order.contact_email),
        'code_sent': False,
        'resend_wait': 0,
        'send_error': '',
        'conflict': request.session.get(_CONFLICT_SESSION_KEY) == order.pk,
        'order_number': order.order_number,
        'next': request.get_full_path(),
        'login_url': f"{reverse('account:login')}?next={reverse('dashboard:orders')}",
    }
    if otp:
        sent_for = request.session.get(SESSION_OTP_SENT_KEY)
        if auto_send and order.create_account_requested and sent_for != order.pk:
            try:
                issue_code(request, order.contact_mobile)
            except OtpError as exc:
                card['send_error'] = str(exc)
            else:
                request.session[SESSION_OTP_SENT_KEY] = order.pk
                sent_for = order.pk
        card['code_sent'] = sent_for == order.pk
        card['resend_wait'] = seconds_until_resend(order.contact_mobile) if card['code_sent'] else 0
    return {'account_card': card}


def create_requested_password_account(request, order):
    """Password mode: create the account the buyer asked for at checkout.

    Runs once, from the paid order's confirmation page in the buyer's own
    session.  Returns a redirect when the account was created and the buyer
    signed in, else ``None`` (no request, or the details already belong to an
    account — then the card asks the buyer to sign in instead).
    """
    pending = dict(request.session.get(SESSION_ACCOUNT_KEY) or {})
    password_hash = pending.pop(str(order.pk), None)
    if password_hash is None:
        return None
    request.session[SESSION_ACCOUNT_KEY] = pending  # one attempt; the hash never lingers
    if order.user_id or not order.create_account_requested or _otp_available():
        return None
    user = create_account_from_order(order, password_hash)
    if user is None:
        request.session[_CONFLICT_SESSION_KEY] = order.pk
        return None
    attach_orders(user, _session_orders_with_contact(request, order.contact_mobile, order.contact_email))
    login(request, user, backend=_LOGIN_BACKEND)
    messages.success(
        request,
        f'حساب کاربری شما ساخته شد و سفارش در آن ثبت شد. برای ورودهای بعدی: نام کاربری {order.contact_mobile} '
        'و رمز عبوری که انتخاب کردید.',
    )
    return redirect('payments:successful_done', order_number=order.order_number)


@never_cache
def guest_order(request, access_token):
    """صفحهٔ سفارش مهمان با لینک محرمانه (پس از پرداخت، در ایمیل و از صفحهٔ پیگیری)."""
    order = Order.objects.filter(access_token=access_token).first() if access_token else None
    if order is None:
        raise Http404('سفارش یافت نشد.')
    if order.user_id:
        # The order now belongs to an account and is protected by its login.
        messages.info(request, 'این سفارش به یک حساب کاربری منتقل شده است؛ برای مشاهده وارد همان حساب شوید.')
        target = reverse('dashboard:order_detail', kwargs={'order_number': order.order_number})
        if request.user.is_authenticated and request.user.pk == order.user_id:
            return redirect(target)
        return redirect(f"{reverse('account:login')}?next={target}")
    grant_order_access(request, order)

    from downloads.models import DownloadToken

    tokens = DownloadToken.objects.filter(order=order).select_related('product', 'order')
    items = []
    raw = order.items_data.get('items', []) if isinstance(order.items_data, dict) else (order.items_data or [])
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict):
            continue
        unit_price = item.get('unit_price') or item.get('price') or 0
        quantity = item.get('quantity') or 1
        items.append({
            'title': item.get('title') or item.get('product_title') or '',
            'unit_price': unit_price,
            'quantity': quantity,
            'total_price': unit_price * quantity,
        })
    cart = order.cart
    from accounts.otp import mask_phone

    context = {
        'order': order,
        'items': items,
        'tokens': tokens,
        'order_link': order_link(request, order),
        'mobile_masked': mask_phone(order.contact_mobile) if order.contact_mobile else '',
        'email_masked': _mask_email(order.contact_email),
        'can_resume_payment': order.status == 'pending' and cart is not None and cart.items.exists()
        and cart.user_id is None and cart.pk == request.session.get('guest_cart_id'),
    }
    context.update(account_card_context(request, order))
    response = render(request, 'cart/guest_order.html', context)
    # The secret link must never leak to another site through the Referer header.
    response['Referrer-Policy'] = 'no-referrer'
    return response


def _safe_next(request, fallback):
    nxt = request.POST.get('next') or ''
    if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()},
                                               require_https=request.is_secure()):
        return nxt
    return fallback


@require_POST
def guest_account(request, order_number):
    """Optional account for a paid guest order, verified with a one-time SMS code."""
    order = get_object_or_404(Order, order_number=order_number)
    if order.user_id or not can_access_order(request, order) or order.status not in Order.COMPLETED_STATUSES:
        raise Http404
    back = _safe_next(request, order_path(order))
    action = request.POST.get('action', '')
    if not _otp_available():
        if action == 'password':
            return _create_account_with_password(request, order, back)
        messages.info(request, 'تأیید پیامکی در حال حاضر فعال نیست؛ با انتخاب رمز عبور حساب بسازید یا وارد حساب شوید.')
        return redirect(back)
    from accounts.otp import OtpError, issue_code, mask_phone, verify_code

    phone = order.contact_mobile
    if action == 'send':
        try:
            issue_code(request, phone)
        except OtpError as exc:
            messages.error(request, str(exc))
        else:
            request.session[SESSION_OTP_SENT_KEY] = order.pk
            messages.success(request, f'کد تأیید به شمارهٔ {mask_phone(phone)} پیامک شد.')
        return redirect(back)
    if action == 'verify':
        try:
            verify_code(request, phone, request.POST.get('code', ''))
            user, created = account_for_verified_phone(phone, order.contact_email)
        except OtpError as exc:
            messages.error(request, str(exc))
            return redirect(back)
        # The phone is now verified: every guest order this session placed with it is theirs.
        attach_orders(user, _session_orders_with_contact(request, mobile=phone))
        request.session.pop(SESSION_OTP_SENT_KEY, None)
        login(request, user, backend=_LOGIN_BACKEND)
        if created:
            messages.success(request, 'حساب کاربری شما ساخته شد و سفارش در آن ثبت شد. ورودهای بعدی با همین شماره و کد پیامکی است.')
        else:
            messages.success(request, 'وارد حساب کاربری‌تان شدید و سفارش به حساب شما اضافه شد.')
        return redirect('dashboard:order_detail', order_number=order.order_number)
    return redirect(back)


def _create_account_with_password(request, order, back):
    """Password mode, after the purchase: the same creation rules as the checkout opt-in."""
    from django.contrib.auth.hashers import make_password
    from django.contrib.auth.password_validation import validate_password
    from django.core.exceptions import ValidationError
    from django.contrib.auth import get_user_model

    password = request.POST.get('password') or ''
    candidate = get_user_model()(username=order.contact_mobile, email=order.contact_email or '')
    try:
        if len(password) < 8:
            raise ValidationError('رمز عبور باید حداقل ۸ کاراکتر باشد.')
        validate_password(password, user=candidate)
    except ValidationError as exc:
        messages.error(request, ' '.join(exc.messages))
        return redirect(back)
    user = create_account_from_order(order, make_password(password))
    if user is None:
        request.session[_CONFLICT_SESSION_KEY] = order.pk
        return redirect(back)
    attach_orders(user, _session_orders_with_contact(request, order.contact_mobile, order.contact_email))
    login(request, user, backend=_LOGIN_BACKEND)
    messages.success(
        request,
        f'حساب کاربری شما ساخته شد و سفارش در آن ثبت شد. برای ورودهای بعدی: نام کاربری {order.contact_mobile} '
        'و رمز عبوری که انتخاب کردید.',
    )
    return redirect('dashboard:order_detail', order_number=order.order_number)


@never_cache
def track_order(request):
    """پیگیری سفارش مهمان با شمارهٔ سفارش + موبایل؛ دسترسی فقط با کد پیامکی یا لینک ایمیلی.

    The response is the same whether or not an order matches, so the page
    cannot be used to discover orders, phone numbers or e-mail addresses.
    """
    from accounts.otp import OtpError, issue_code, mask_phone, verify_code
    from notifications.sms import normalize_mobile

    otp = _otp_available()
    state = request.session.get(_TRACK_SESSION_KEY) or None
    status = 200
    if request.method == 'POST':
        action = request.POST.get('action', 'lookup')
        if action == 'reset':
            request.session.pop(_TRACK_SESSION_KEY, None)
            return redirect('cart:track_order')
        if action == 'lookup':
            number = re.sub(r'\D', '', _latin_digits(request.POST.get('order_number', '')))[:10]
            mobile = normalize_mobile(request.POST.get('mobile', ''))
            throttle = get_throttle('order_lookup')
            if throttle.is_throttled(request, number):
                messages.error(request, 'تعداد تلاش‌ها زیاد است. لطفاً چند دقیقه دیگر دوباره امتحان کنید.')
                status = 429
            elif not number or not mobile:
                messages.error(request, 'شمارهٔ سفارش و شماره موبایلی را که هنگام خرید وارد کردید درست بنویسید.')
                status = 400
            else:
                throttle.record(request, number)
                order = Order.objects.filter(order_number=number, user__isnull=True, contact_mobile=mobile).first()
                if otp:
                    if order is not None:
                        try:
                            issue_code(request, mobile)
                        except OtpError as exc:  # same answer either way; the buyer can retry
                            logger.info('Order-tracking code for %s not sent: %s', order.pk, exc)
                    request.session[_TRACK_SESSION_KEY] = {'mobile': mobile, 'order': order.pk if order else None}
                    messages.info(request, f'اگر سفارشی با این مشخصات ثبت شده باشد، کد تأیید به شمارهٔ {mask_phone(mobile)} پیامک شد.')
                else:
                    if order is not None and order.contact_email:
                        from notifications.services import schedule_guest_order_email

                        schedule_guest_order_email(order.pk, order_link(request, order), reminder=True)
                    messages.info(
                        request,
                        'اگر سفارشی با این مشخصات ثبت شده و هنگام خرید ایمیل وارد شده باشد، لینک صفحهٔ سفارش '
                        'به همان ایمیل فرستاده شد. در غیر این صورت با پشتیبانی تماس بگیرید.',
                    )
                return redirect('cart:track_order')
        elif action == 'verify' and state and otp:
            order_pk = state.get('order')
            code = request.POST.get('code', '')
            verified = False
            if order_pk is not None:
                try:
                    verify_code(request, state.get('mobile', ''), code)
                    verified = True
                except OtpError:
                    verified = False
            if not verified:
                messages.error(request, _GENERIC_CODE_ERROR)
                status = 400
            else:
                request.session.pop(_TRACK_SESSION_KEY, None)
                order = Order.objects.filter(pk=order_pk).first()
                if order is None or not order.access_token:
                    raise Http404
                # ``guest_order`` grants this session access (or sends an order
                # that has since moved into an account to that account's login).
                return redirect('cart:guest_order', access_token=order.access_token)
        state = request.session.get(_TRACK_SESSION_KEY) or None
    return render(request, 'cart/track_order.html', {
        'otp_available': otp,
        'lookup': state,
        'mobile_masked': mask_phone(state['mobile']) if state else '',
    }, status=status)


def _latin_digits(value):
    from core.persian_digits import to_latin_digits

    return to_latin_digits(str(value or ''))
