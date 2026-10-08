import re

from django import forms

from .models import ServiceRequest


_DIGIT_TRANSLATION = str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789')


def _normalise_iran_phone(value):
    phone = (value or '').strip().translate(_DIGIT_TRANSLATION).replace(' ', '').replace('-', '')
    if phone.startswith('+98'):
        phone = '0' + phone[3:]
    elif phone.startswith('0098'):
        phone = '0' + phone[4:]
    elif len(phone) == 10 and phone.startswith('9'):
        phone = '0' + phone
    return phone


class ServiceRequestForm(forms.ModelForm):
    """Validation shared by the public AJAX form and any future admin-facing form."""

    phone = forms.CharField(
        max_length=14,
        widget=forms.TextInput(attrs={'type': 'tel', 'autocomplete': 'tel', 'inputmode': 'tel', 'dir': 'ltr'}),
    )

    class Meta:
        model = ServiceRequest
        fields = ('full_name', 'phone', 'email', 'package', 'project_type', 'budget', 'message')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['package'].queryset = self.fields['package'].queryset.filter(is_active=True)

    def clean_full_name(self):
        value = (self.cleaned_data.get('full_name') or '').strip()
        if len(value) < 3:
            raise forms.ValidationError('نام و نام خانوادگی باید حداقل ۳ کاراکتر داشته باشد.')
        return value

    def clean_phone(self):
        phone = _normalise_iran_phone(self.cleaned_data.get('phone'))
        if not re.fullmatch(r'09\d{9}', phone):
            raise forms.ValidationError('شماره تماس را به‌صورت یک شماره موبایل معتبر وارد کنید.')
        return phone

    def clean_message(self):
        value = (self.cleaned_data.get('message') or '').strip()
        if len(value) < 10:
            raise forms.ValidationError('توضیحات پروژه باید حداقل ۱۰ کاراکتر داشته باشد.')
        return value
