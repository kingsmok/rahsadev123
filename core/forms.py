import re

from django import forms
from django.core.exceptions import ValidationError

from .models import ContactUs


_DIGIT_TRANSLATION = str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789')


def _normalise_iran_phone(value):
    """Accept Persian/Arabic digits and common Iranian mobile prefixes."""
    phone = (value or '').strip().translate(_DIGIT_TRANSLATION).replace(' ', '').replace('-', '')
    if phone.startswith('+98'):
        phone = '0' + phone[3:]
    elif phone.startswith('0098'):
        phone = '0' + phone[4:]
    elif len(phone) == 10 and phone.startswith('9'):
        phone = '0' + phone
    return phone


class ContactUsForm(forms.ModelForm):
    """Contact form with explicit, reusable validation and accessible widgets."""

    phone = forms.CharField(
        max_length=14,
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
        phone = _normalise_iran_phone(self.cleaned_data.get('phone'))
        if not re.fullmatch(r'09\d{9}', phone):
            raise ValidationError('شماره تماس را به‌صورت یک شماره موبایل معتبر وارد کنید.')
        return phone

    def clean_message(self):
        message = (self.cleaned_data.get('message') or '').strip()
        if len(message) < 10:
            raise ValidationError('متن پیام باید حداقل ۱۰ کاراکتر داشته باشد.')
        return message
