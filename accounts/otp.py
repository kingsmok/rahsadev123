"""ورود و ثبت‌نام با کد یک‌بارمصرف پیامکی (sms.ir)."""
import logging
import secrets
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.validators import validate_ipv46_address
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac

from core.ratelimit import Throttle, _cache_key, _increment

from .models import PhoneOTP, Profile

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 5
RESEND_COOLDOWN_SECONDS = 60
SEND_WINDOW_SECONDS = 15 * 60
SENDS_PER_PHONE = 4       # per window, per phone + address
SENDS_PER_ADDRESS = 12    # per window, per address
SENDS_PER_PHONE_GLOBAL = 6  # per window, per phone from any address (SMS bombing)
VERIFY_PER_ADDRESS = 30


class OtpError(Exception):
    pass


def _send_throttle():
    return Throttle(namespace='otp.send', limit=SENDS_PER_PHONE, window_seconds=SEND_WINDOW_SECONDS,
                    ip_limit=SENDS_PER_ADDRESS)


def _verify_throttle():
    return Throttle(namespace='otp.verify', limit=MAX_ATTEMPTS * 3, window_seconds=SEND_WINDOW_SECONDS,
                    ip_limit=VERIFY_PER_ADDRESS)


def _client_ip(request):
    address = request.META.get('REMOTE_ADDR') or ''
    try:
        validate_ipv46_address(address)
    except ValidationError:
        return None
    return address


def _phone_counter_key(phone):
    return _cache_key('otp.send.phone', phone)


def hash_code(phone, code):
    return salted_hmac('accounts.otp.v1', f'{phone}:{code}').hexdigest()


def mask_phone(phone):
    return f'{phone[:4]}***{phone[-4:]}' if len(phone) >= 8 else phone


def seconds_until_resend(phone):
    last = PhoneOTP.objects.filter(phone=phone).order_by('-created_at').values_list('created_at', flat=True).first()
    if not last:
        return 0
    remaining = RESEND_COOLDOWN_SECONDS - (timezone.now() - last).total_seconds()
    return max(0, int(remaining + 0.999))


def issue_code(request, phone):
    """Create, store (hashed) and SMS a new code. Raises :class:`OtpError`."""
    from notifications.models import SmsSettings
    from notifications.sms import SmsError, SmsIrClient

    config = SmsSettings.load()
    if not config.otp_available:
        raise OtpError('ورود با پیامک در حال حاضر فعال نیست.')

    throttle = _send_throttle()
    if throttle.is_throttled(request, phone) or cache.get(_phone_counter_key(phone), 0) >= SENDS_PER_PHONE_GLOBAL:
        raise OtpError('تعداد درخواست کد زیاد است. لطفاً چند دقیقه دیگر دوباره تلاش کنید.')
    wait = seconds_until_resend(phone)
    if wait:
        raise OtpError(f'کد قبلی همین حالا ارسال شده است؛ {wait} ثانیه دیگر می‌توانید دوباره درخواست کنید.')
    throttle.record(request, phone)
    _increment(_phone_counter_key(phone), SEND_WINDOW_SECONDS)

    code = ''.join(secrets.choice('0123456789') for _ in range(config.otp_length))
    now = timezone.now()
    with transaction.atomic():
        PhoneOTP.objects.filter(phone=phone, consumed_at__isnull=True).update(consumed_at=now)
        otp = PhoneOTP.objects.create(
            phone=phone,
            code_hash=hash_code(phone, code),
            expires_at=now + timedelta(seconds=config.otp_ttl_seconds),
            ip_address=_client_ip(request),
        )
    try:
        SmsIrClient(config.api_key).send_verify(phone, config.otp_template_id, {config.otp_parameter: code})
    except SmsError as exc:
        otp.delete()
        logger.warning('OTP SMS to %s failed: %s', mask_phone(phone), exc)
        raise OtpError('ارسال پیامک انجام نشد. لطفاً کمی بعد دوباره تلاش کنید.') from exc
    return otp


def verify_code(request, phone, code):
    """Return the matching, now-consumed :class:`PhoneOTP` or raise :class:`OtpError`."""
    throttle = _verify_throttle()
    if throttle.is_throttled(request, phone):
        raise OtpError('تعداد تلاش‌ها زیاد است. لطفاً چند دقیقه دیگر دوباره تلاش کنید.')
    throttle.record(request, phone)

    code = (code or '').strip()
    otp = (PhoneOTP.objects
           .filter(phone=phone, consumed_at__isnull=True, expires_at__gt=timezone.now())
           .order_by('-created_at').first())
    if otp is None:
        raise OtpError('کد منقضی شده یا وجود ندارد. لطفاً کد جدید درخواست کنید.')
    if otp.attempts >= MAX_ATTEMPTS:
        PhoneOTP.objects.filter(pk=otp.pk).update(consumed_at=timezone.now())
        raise OtpError('تعداد تلاش‌های نادرست زیاد بود. لطفاً کد جدید درخواست کنید.')
    PhoneOTP.objects.filter(pk=otp.pk).update(attempts=F('attempts') + 1)
    if not code.isdigit() or not constant_time_compare(otp.code_hash, hash_code(phone, code)):
        raise OtpError('کد واردشده درست نیست.')
    # Consume atomically: a second request with the same code loses the race.
    consumed = PhoneOTP.objects.filter(pk=otp.pk, consumed_at__isnull=True).update(consumed_at=timezone.now())
    if not consumed:
        raise OtpError('این کد قبلاً استفاده شده است. لطفاً کد جدید درخواست کنید.')
    return otp


def user_for_phone(phone):
    """Existing user with this verified phone, or a new one. Raises :class:`OtpError`."""
    User = get_user_model()
    profiles = list(Profile.objects.filter(phone=phone).select_related('user')[:2])
    if len(profiles) > 1:
        raise OtpError('این شماره به بیش از یک حساب متصل است؛ لطفاً با نام کاربری و رمز عبور وارد شوید.')
    if profiles:
        user = profiles[0].user
        if not user.is_active:
            raise OtpError('این حساب غیرفعال است. با پشتیبانی تماس بگیرید.')
        return user, False

    username = phone
    suffix = 1
    while User.objects.filter(username__iexact=username).exists():
        suffix += 1
        username = f'{phone}_{suffix}'
    try:
        with transaction.atomic():
            user = User(username=username)
            user.set_unusable_password()
            user.save()
            Profile.objects.update_or_create(user=user, defaults={'phone': phone})
    except IntegrityError as exc:  # pragma: no cover - concurrent sign-up with same username
        raise OtpError('ساخت حساب انجام نشد؛ لطفاً دوباره تلاش کنید.') from exc
    return user, True
