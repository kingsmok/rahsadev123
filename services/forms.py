from django import forms
from django.core.validators import RegexValidator

from .models import ServiceRequest


class ServiceRequestForm(forms.ModelForm):
    """Validation shared by the public AJAX form and any future admin-facing form."""

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
        phone = (self.cleaned_data.get('phone') or '').strip().replace(' ', '').replace('-', '')
        if phone.startswith('+98'):
            phone = '0' + phone[3:]
        elif phone.startswith('0098'):
            phone = '0' + phone[4:]
        elif len(phone) == 10 and phone.startswith('9'):
            phone = '0' + phone
        return phone

    def clean_message(self):
        value = (self.cleaned_data.get('message') or '').strip()
        if len(value) < 10:
            raise forms.ValidationError('توضیحات پروژه باید حداقل ۱۰ کاراکتر داشته باشد.')
        return value
