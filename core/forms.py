from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator

from .models import ContactUs


class ContactUsForm(forms.ModelForm):
    """Contact form with explicit, reusable validation and accessible widgets."""

    phone = forms.CharField(
        max_length=14,
        validators=[
            RegexValidator(
                regex=r'^(?:\+98|0098|0)?9\d{9}$',
                message='شماره تماس را به‌صورت یک شماره موبایل معتبر وارد کنید.',
            )
        ],
        widget=forms.TextInput(attrs={'type': 'tel', 'autocomplete': 'tel', 'inputmode': 'tel', 'dir': 'ltr'}),
    )

    class Meta:
        model = ContactUs
        fields = ('first_name', 'last_name', 'phone', 'message')
        widgets = {
            'first_name': forms.TextInput(attrs={'autocomplete': 'given-name'}),
            'last_name': forms.TextInput(attrs={'autocomplete': 'family-name'}),
            'phone': forms.TextInput(attrs={'type': 'tel', 'autocomplete': 'tel', 'inputmode': 'tel', 'dir': 'ltr'}),
            'message': forms.Textarea(attrs={'rows': 5}),
        }

    def clean_first_name(self):
        return self._clean_name('first_name', 'نام')

    def clean_last_name(self):
        return self._clean_name('last_name', 'نام خانوادگی')

    def _clean_name(self, field, label):
        value = (self.cleaned_data.get(field) or '').strip()
        if len(value) < 2:
            raise ValidationError(f'{label} باید حداقل ۲ کاراکتر داشته باشد.')
        return value

    def clean_phone(self):
        phone = (self.cleaned_data.get('phone') or '').strip().replace(' ', '').replace('-', '')
        if phone.startswith('+98'):
            phone = '0' + phone[3:]
        elif phone.startswith('0098'):
            phone = '0' + phone[4:]
        elif len(phone) == 10 and phone.startswith('9'):
            phone = '0' + phone
        return phone

    def clean_message(self):
        message = (self.cleaned_data.get('message') or '').strip()
        if len(message) < 10:
            raise ValidationError('متن پیام باید حداقل ۱۰ کاراکتر داشته باشد.')
        return message
