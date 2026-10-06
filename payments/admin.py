from django.contrib import admin
from .models import GatewaySettings, PaymentTransaction


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = ('order', 'gateway', 'amount', 'status', 'ref_id', 'created_at')
    list_filter = ('gateway', 'status', 'created_at')
    search_fields = ('order__order_number', 'authority', 'ref_id')
    readonly_fields = ('created_at', 'updated_at', 'raw_response')


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
