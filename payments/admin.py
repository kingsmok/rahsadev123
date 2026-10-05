from django.contrib import admin
from .models import PaymentTransaction


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = ('order', 'gateway', 'amount', 'status', 'ref_id', 'created_at')
    list_filter = ('gateway', 'status', 'created_at')
    search_fields = ('order__order_number', 'authority', 'ref_id')
    readonly_fields = ('created_at', 'updated_at', 'raw_response')
