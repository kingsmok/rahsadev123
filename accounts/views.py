from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth import views as auth_views
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from core.throttling import get_throttle

from .forms import LoginForm, UserRegistrationForm
from .otp import OtpError, issue_code, mask_phone, seconds_until_resend, user_for_phone, verify_code
from .security import (
    clear_login_failures,
    login_is_throttled,
    password_reset_is_throttled,
    record_failed_login,
    record_password_reset_request,
)


def _safe_next(request):
    """مقصد بازگشت بعد از ورود — فقط مسیرهای داخلی پذیرفته می‌شوند."""
    nxt = request.POST.get('next') or request.GET.get('next')
    if nxt and url_has_allowed_host_and_scheme(
        nxt, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return nxt
    return None


def user_register(request):
    if request.user.is_authenticated:
        return redirect('core:home')

    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        # ساخت حساب ناشناس و نامحدود است؛ بدون سقف، یک اسکریپت می‌تواند
        # هزاران حساب جعلی بسازد. همان الگوی بقیهٔ POSTهای عمومی اعمال می‌شود.
        throttle = get_throttle('register')
        identity = form.data.get('username', '')
        if throttle.is_throttled(request, identity):
            throttle.record(request, identity)
            form.add_error(None, 'تعداد تلاش‌های ثبت‌نام زیاد است. لطفاً چند دقیقه دیگر دوباره امتحان کنید.')
            return render(request, 'accounts/register.html', {'form': form}, status=429)
        throttle.record(request, identity)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])
            user.save()
            messages.success(request, 'حساب شما ساخته شد. حالا می‌توانید وارد شوید.')
            return redirect('account:login')
    else:
        form = UserRegistrationForm()

    return render(request, 'accounts/register.html', {'form': form, 'otp_available': _otp_available()})


def user_login(request):
    if request.user.is_authenticated:
        return redirect('core:home')

    if request.method == 'POST':
        form = LoginForm(request.POST)
        username = form.data.get('username', '')
        if login_is_throttled(request, username):
            form.add_error(None, 'تعداد تلاش‌های ناموفق زیاد است. لطفاً چند دقیقه دیگر دوباره امتحان کنید.')
        elif form.is_valid():
            user = form.get_user()
            clear_login_failures(request, username)
            login(request, user)
            messages.success(request, f'خوش آمدید {user.get_full_name() or user.username}!')
            return redirect(_safe_next(request) or 'core:home')
        else:
            record_failed_login(request, username)
    else:
        form = LoginForm()

    return render(request, 'accounts/login.html', {'form': form, 'otp_available': _otp_available()})


@require_POST
def user_logout(request):
    logout(request)
    messages.info(request, 'از حساب کاربری خارج شدید.')
    return redirect('core:home')


class ThrottledPasswordResetView(auth_views.PasswordResetView):
    """بازیابی رمز عبور جنگو با محدودسازی نرخ درخواست.

    رفتار ضد شمارشِ خودِ جنگو حفظ می‌شود: چه ایمیل وجود داشته باشد چه نه،
    و چه درخواست محدود شده باشد چه نه، کاربر همیشه همان صفحهٔ «لینک ارسال
    شد» را می‌بیند؛ وقتی محدودسازی فعال است فقط ایمیل واقعاً ارسال نمی‌شود.
    """

    def post(self, request, *args, **kwargs):
        email = (request.POST.get('email') or '').strip()
        if email and password_reset_is_throttled(request, email):
            return redirect('account:password_reset_done')
        if email:
            record_password_reset_request(request, email)
        # نام سایت در ایمیل از تنظیمات سایت می‌آید، نه از دامنهٔ درخواست.
        from core.branding import get_brand

        self.extra_email_context = {'site_name': get_brand(request).name}
        return super().post(request, *args, **kwargs)


def _otp_available():
    try:
        from notifications.models import SmsSettings

        return SmsSettings.load().otp_available
    except Exception:  # tables missing during a first migrate
        return False


_OTP_SESSION_KEY = 'otp_phone'


def otp_login(request):
    """ورود و ثبت‌نام با شماره موبایل و کد یک‌بارمصرف پیامکی (sms.ir)."""
    from notifications.sms import normalize_mobile

    if request.user.is_authenticated:
        return redirect('core:home')
    if not _otp_available():
        messages.info(request, 'ورود با پیامک در حال حاضر فعال نیست؛ با نام کاربری و رمز عبور وارد شوید.')
        return redirect('account:login')

    phone = request.session.get(_OTP_SESSION_KEY, '')
    status = 200
    if request.method == 'POST':
        action = request.POST.get('action', '')
        if action == 'change':
            request.session.pop(_OTP_SESSION_KEY, None)
            return redirect(_otp_url(request))
        if action in ('send', 'resend'):
            if action == 'send':
                phone = normalize_mobile(request.POST.get('phone', ''))
            if not phone:
                messages.error(request, 'شماره موبایل معتبر نیست؛ مثلاً 09121234567 را وارد کنید.')
                status = 400
            else:
                try:
                    issue_code(request, phone)
                except OtpError as exc:
                    messages.error(request, str(exc))
                    status = 429 if 'زیاد' in str(exc) else 400
                    if action == 'send' and not request.session.get(_OTP_SESSION_KEY):
                        phone = ''
                else:
                    request.session[_OTP_SESSION_KEY] = phone
                    messages.success(request, f'کد تأیید به شمارهٔ {mask_phone(phone)} پیامک شد.')
                    return redirect(_otp_url(request))
        elif action == 'verify' and phone:
            try:
                verify_code(request, phone, request.POST.get('code', ''))
                user, created = user_for_phone(phone)
            except OtpError as exc:
                messages.error(request, str(exc))
                status = 400
            else:
                request.session.pop(_OTP_SESSION_KEY, None)
                login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                if created:
                    messages.success(request, 'حساب شما با شماره موبایل ساخته شد. می‌توانید نام و ایمیل خود را در پروفایل تکمیل کنید.')
                    return redirect(_safe_next(request) or 'dashboard:home')
                messages.success(request, f'خوش آمدید {user.get_full_name() or user.username}!')
                return redirect(_safe_next(request) or 'core:home')

    return render(request, 'accounts/otp_login.html', {
        'otp_phone': phone,
        'otp_phone_masked': mask_phone(phone) if phone else '',
        'resend_wait': seconds_until_resend(phone) if phone else 0,
        'next': _safe_next(request) or '',
    }, status=status)


def _otp_url(request):
    from django.urls import reverse
    from urllib.parse import urlencode

    url = reverse('account:otp_login')
    nxt = _safe_next(request)
    return f'{url}?{urlencode({"next": nxt})}' if nxt else url
