import re

from django import forms
from django.core.exceptions import ValidationError

from core.persian_digits import normalise_iran_phone
from .models import ContactUs


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
        phone = normalise_iran_phone(self.cleaned_data.get('phone'))
        if not re.fullmatch(r'09\d{9}', phone):
            raise ValidationError('شماره تماس را به‌صورت یک شماره موبایل معتبر وارد کنید.')
        return phone

    def clean_message(self):
        message = (self.cleaned_data.get('message') or '').strip()
        if len(message) < 10:
            raise ValidationError('متن پیام باید حداقل ۱۰ کاراکتر داشته باشد.')
        return message
