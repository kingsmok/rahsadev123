from django.contrib import admin
from .models import GatewaySettings, PaymentTransaction

from core.admin_utils import EnhancedAdminMixin
from jalali_date import datetime2jalali


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(EnhancedAdminMixin, admin.ModelAdmin):
    list_display = ('order_number', 'gateway', 'amount', 'status', 'ref_id', 'get_created_at_jalali')
    list_filter = ('gateway', 'status', 'created_at')
    search_fields = ('order__order_number', 'authority', 'ref_id')
    readonly_fields = ('order', 'gateway', 'authority', 'ref_id', 'amount', 'status',
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


@admin.register(GatewaySettings)
class GatewaySettingsAdmin(admin.ModelAdmin):
    list_display = ('key', 'title', 'is_enabled', 'is_configured', 'is_sandbox', 'updated_at')
    list_editable = ('is_enabled', 'is_sandbox')
    list_filter = ('is_enabled',)
    search_fields = ('title', 'merchant_id')
    fieldsets = (
        ('وضعیت', {
            'fields': ('key', 'title', 'is_enabled', 'is_sandbox', 'order')
        }),
        ('اطلاعات اتصال', {
            'fields': ('merchant_id', 'client_id', 'client_secret'),
            'description': 'فیلدهای هر درگاه را فقط در صورت نیاز پر کنید. مقادیر خالی از متغیرهای محیطی خوانده می‌شوند.'
        }),
        ('نمایش در سایت', {
            'fields': ('description',)
        }),
    )

    @admin.display(description='اطلاعات اتصال ثبت شده؟', boolean=True)
    def is_configured(self, obj):
        return obj.is_configured
