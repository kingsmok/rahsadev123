"""اطلاعات خریدار مهمان در صفحهٔ پرداخت (حداقلِ لازم: موبایل؛ ایمیل اختیاری)."""
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError


class GuestCheckoutForm(forms.Form):
    mobile = forms.CharField(max_length=20, required=False)
    email = forms.EmailField(
        max_length=254, required=False,
        error_messages={'invalid': 'ایمیل واردشده معتبر نیست؛ مثل name@example.com'},
    )
    create_account = forms.BooleanField(required=False)
    password = forms.CharField(required=False, strip=False, max_length=128)

    def __init__(self, *args, password_mode=False, **kwargs):
        """``password_mode``: SMS codes are unavailable, so an optional account needs a password."""
        super().__init__(*args, **kwargs)
        self.password_mode = password_mode

    def clean_mobile(self):
        from notifications.sms import normalize_mobile

        raw = (self.cleaned_data.get('mobile') or '').strip()
        if not raw:
            raise ValidationError('شماره موبایل را وارد کنید؛ رسید و پیگیری سفارش با همین شماره انجام می‌شود.')
        mobile = normalize_mobile(raw)
        if not mobile:
            raise ValidationError('شماره موبایل معتبر نیست؛ مثل 09121234567')
        return mobile

    def clean_email(self):
        return (self.cleaned_data.get('email') or '').strip().lower()

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('create_account') and self.password_mode:
            password = cleaned.get('password') or ''
            if not password:
                self.add_error('password', 'برای ساخت حساب یک رمز عبور انتخاب کنید (حداقل ۸ کاراکتر).')
            else:
                candidate = get_user_model()(
                    username=cleaned.get('mobile') or '', email=cleaned.get('email') or '',
                )
                try:
                    validate_password(password, user=candidate)
                except ValidationError as exc:
                    self.add_error('password', exc)
        return cleaned

    def error_dict(self):
        """First message per field, JSON-serialisable for the session (PRG)."""
        return {field: str(errors[0]) for field, errors in self.errors.items() if errors}
