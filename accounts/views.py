from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.models import User
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .forms import LoginForm, UserRegistrationForm
from .security import clear_login_failures, login_is_throttled, record_failed_login


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
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])
            user.save()
            messages.success(request, 'حساب شما ساخته شد. حالا می‌توانید وارد شوید.')
            return redirect('account:login')
    else:
        form = UserRegistrationForm()

    return render(request, 'accounts/register.html', {'form': form})


def user_login(request):
    if request.user.is_authenticated:
        return redirect('core:home')

    if request.method == 'POST':
        form = LoginForm(request.POST)
        username = form.data.get('username', '')
        if login_is_throttled(request, username):
            form.add_error(None, 'تعداد تلاش‌های ناموفق زیاد است. لطفاً چند دقیقه دیگر دوباره امتحان کنید.')
        elif form.is_valid():
            user = User.objects.get(username=form.cleaned_data.get('username'))
            clear_login_failures(request, username)
            login(request, user)
            messages.success(request, f'خوش آمدید {user.get_full_name() or user.username}!')
            return redirect(_safe_next(request) or 'core:home')
        else:
            record_failed_login(request, username)
    else:
        form = LoginForm()

    return render(request, 'accounts/login.html', {'form': form})


@require_POST
def user_logout(request):
    logout(request)
    messages.info(request, 'از حساب کاربری خارج شدید.')
    return redirect('core:home')
