from django import forms
from django.conf import settings
from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import GatewaySettings, PaymentTransaction

from core.admin_utils import EnhancedAdminMixin
from jalali_date import datetime2jalali


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(EnhancedAdminMixin, admin.ModelAdmin):
    list_display = ('order_number', 'gateway', 'amount', 'status', 'ref_id', 'get_created_at_jalali')
    list_filter = ('gateway', 'status', 'created_at')
    search_fields = ('order__order_number', 'authority', 'ref_id', 'reference_id')
    readonly_fields = ('order', 'gateway', 'authority', 'reference_id', 'ref_id', 'amount', 'status',
                       'created_at', 'updated_at', 'raw_response')
    date_hierarchy = 'created_at'
    list_select_related = ('order',)
    csv_filename = 'masaishop-payments.csv'
    list_per_page = 40

    @admin.display(description='شماره سفارش', ordering='order__order_number')
    def order_number(self, obj):
        return obj.order.order_number

    @admin.display(description='زمان ایجاد', ordering='created_at')
    def get_created_at_jalali(self, obj):
        return datetime2jalali(obj.created_at).strftime('%Y/%m/%d — %H:%M')


class GatewaySettingsForm(forms.ModelForm):
    """رمزها هرگز دوباره در فرم نمایش داده نمی‌شوند؛ خالی گذاشتن = حفظ مقدار قبلی."""

    SECRET_FIELDS = ('client_secret', 'password')

    client_secret = forms.CharField(
        required=False, label='Client Secret',
        widget=forms.PasswordInput(render_value=False, attrs={'autocomplete': 'new-password'}),
        help_text='اسنپ‌پی و ترب‌پی. برای تغییر مقدار جدید را وارد کنید؛ خالی = حفظ مقدار فعلی.')
    password = forms.CharField(
        required=False, label='رمز عبور API',
        widget=forms.PasswordInput(render_value=False, attrs={'autocomplete': 'new-password'}),
        help_text='اسنپ‌پی و ترب‌پی. برای تغییر مقدار جدید را وارد کنید؛ خالی = حفظ مقدار فعلی.')

    class Meta:
        model = GatewaySettings
        fields = '__all__'

    def clean_api_base_url(self):
        value = (self.cleaned_data.get('api_base_url') or '').strip().rstrip('/')
        if value and not value.startswith('https://'):
            raise forms.ValidationError('آدرس API باید با https:// شروع شود.')
        return value

    def save(self, commit=True):
        instance = super().save(commit=False)
        if instance.pk:
            stored = GatewaySettings.objects.filter(pk=instance.pk).values(*self.SECRET_FIELDS).first() or {}
            for name in self.SECRET_FIELDS:
                if not self.cleaned_data.get(name):
                    setattr(instance, name, stored.get(name, ''))
        if commit:
            instance.save()
        return instance


@admin.register(GatewaySettings)
class GatewaySettingsAdmin(admin.ModelAdmin):
    form = GatewaySettingsForm
    list_display = ('logo', 'key', 'title', 'is_enabled', 'is_configured', 'is_sandbox', 'order', 'updated_at')
    list_display_links = ('key',)
    list_editable = ('is_enabled', 'is_sandbox', 'order')
    list_filter = ('is_enabled',)
    search_fields = ('title', 'merchant_id')
    readonly_fields = ('callback_url', 'secret_status')
    fieldsets = (
        ('وضعیت', {
            'fields': ('key', 'title', 'is_enabled', 'is_sandbox', 'order')
        }),
        ('اطلاعات اتصال', {
            'fields': ('merchant_id', 'client_id', 'client_secret', 'username', 'password', 'secret_status',
                       'api_base_url', 'service_slug', 'callback_url'),
            'description': format_html(
                '<b>زرین‌پال:</b> مرچنت کد. <b>زرین‌پلاس:</b> توکن پذیرنده در «مرچنت کد / توکن». '
                '<b>اسنپ‌پی:</b> Client ID، Client Secret، نام کاربری، رمز و آدرس پایهٔ API (از اسنپ‌پی). '
                '<b>ترب‌پی:</b> Client ID، Client Secret، نام کاربری و رمز (از تیکت «مرجع ثبت‌نام ترب‌پی»). '
                'مقادیر خالی از متغیرهای محیطی خوانده می‌شوند. برای اسنپ‌پی، IP سرور و «آدرس بازگشت» باید نزد اسنپ‌پی ثبت شود.'
            ),
        }),
        ('نمایش در سایت', {
            'fields': ('description',)
        }),
    )

    @admin.display(description='اطلاعات اتصال ثبت شده؟', boolean=True)
    def is_configured(self, obj):
        return obj.is_configured

    @admin.display(description='')
    def logo(self, obj):
        from django.templatetags.static import static

        return format_html('<img src="{}" alt="" style="height:26px;max-width:70px;object-fit:contain">',
                           static(obj.logo_static_path))

    @admin.display(description='وضعیت رمزها')
    def secret_status(self, obj):
        if not obj or not obj.pk:
            return '—'
        parts = [
            f"Client Secret: {'ثبت شده' if obj.client_secret else 'ثبت نشده'}",
            f"رمز API: {'ثبت شده' if obj.password else 'ثبت نشده'}",
        ]
        return ' — '.join(parts)

    @admin.display(description='آدرس بازگشت (Callback) برای ثبت نزد درگاه')
    def callback_url(self, obj):
        if not obj or not obj.key:
            return '—'
        if obj.key == 'zarinpal':
            path = reverse('payments:callback')
        else:
            path = reverse('payments:gateway_callback', args=[obj.key])
        base = getattr(settings, 'SITE_URL', '') or 'https://دامنه-سایت-شما'
        return format_html('<code dir="ltr">{}{}</code>', base, path)
