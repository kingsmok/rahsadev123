from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator


class UserRegistrationForm(forms.ModelForm):
    """Registration form with server-side validation for every client-side field."""

    first_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'input_second input_all', 'placeholder': 'نام'}),
    )
    last_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'input_second input_all', 'placeholder': 'نام خانوادگی'}),
    )
    username = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'input_second input_all', 'placeholder': 'نام کاربری'}),
    )
    email = forms.CharField(
        max_length=100,
        widget=forms.EmailInput(attrs={'class': 'input_second input_all', 'placeholder': 'ایمیل'}),
        validators=[EmailValidator(message='لطفاً یک ایمیل معتبر وارد کنید.')],
    )
    password = forms.CharField(
        min_length=8,
        max_length=128,
        widget=forms.PasswordInput(attrs={'class': 'input_second input_all', 'placeholder': 'رمز عبور'}),
    )
    agree = forms.BooleanField(
        required=True,
        error_messages={'required': 'برای ساخت حساب باید شرایط و قوانین را بپذیرید.'},
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'username', 'email', 'password']

    def clean_username(self):
        username = (self.cleaned_data.get('username') or '').strip()
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError('این نام کاربری از قبل ثبت شده است.')
        return username

    def clean_email(self):
        email = (self.cleaned_data.get('email') or '').strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError('این ایمیل از قبل ثبت شده است.')
        return email

    def clean_password(self):
        password = self.cleaned_data.get('password')
        # Use Django's configured validators as well as the explicit form limits.
        candidate = User(
            username=self.cleaned_data.get('username', ''),
            email=self.cleaned_data.get('email', ''),
            first_name=self.cleaned_data.get('first_name', ''),
            last_name=self.cleaned_data.get('last_name', ''),
        )
        validate_password(password, user=candidate)
        return password


class LoginForm(forms.Form):
    username = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'input_second input_all', 'placeholder': 'نام کاربری'}),
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'input_second input_all', 'placeholder': 'رمز عبور'}),
    )

    def clean(self):
        cleaned_data = super().clean()
        username = cleaned_data.get('username')
        password = cleaned_data.get('password')

        if username and password:
            user = authenticate(username=username, password=password)
            if user is None:
                raise ValidationError('نام کاربری یا رمز عبور نادرست است.', code='invalid_info')
            if not user.is_active:
                raise ValidationError('این حساب کاربری غیرفعال است.', code='inactive')
            self.user_cache = user
        return cleaned_data


class ChangePasswordForm(forms.Form):
    old_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'input_second input_all', 'placeholder': 'رمز عبور فعلی'}),
    )
    new_password = forms.CharField(
        min_length=8,
        max_length=128,
        widget=forms.PasswordInput(attrs={'class': 'input_second input_all', 'placeholder': 'رمز عبور جدید'}),
    )
    confirm_new_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'input_second input_all', 'placeholder': 'تکرار رمز عبور جدید'}),
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_old_password(self):
        old_password = self.cleaned_data['old_password']
        if self.user and not self.user.check_password(old_password):
            raise ValidationError('رمز عبور فعلی نادرست است.')
        return old_password

    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get('new_password')
        confirm_new_password = cleaned_data.get('confirm_new_password')
        if new_password and confirm_new_password and new_password != confirm_new_password:
            self.add_error('confirm_new_password', 'رمز عبور جدید و تکرار آن مطابقت ندارند.')
        if new_password and not self.errors.get('confirm_new_password'):
            validate_password(new_password, user=self.user)
        return cleaned_data
