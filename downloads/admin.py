from django.contrib import admin
from .models import DownloadToken

from core.admin_utils import EnhancedAdminMixin
from jalali_date import datetime2jalali


@admin.register(DownloadToken)
class DownloadTokenAdmin(EnhancedAdminMixin, admin.ModelAdmin):
    list_display = ('product', 'user', 'order', 'download_count', 'max_downloads', 'is_active',
                    'get_expires_at_jalali', 'get_created_at_jalali')
    list_filter = ('is_active', 'created_at')
    search_fields = ('token', 'user__username', 'product__title', 'order__order_number')
    readonly_fields = ('token', 'download_count', 'created_at')
    autocomplete_fields = ('user', 'product', 'order')
    date_hierarchy = 'created_at'
    list_select_related = ('user', 'product', 'order')
    list_editable = ('is_active',)
    csv_filename = 'masaishop-download-tokens.csv'

    @admin.display(description='انقضا', ordering='expires_at')
    def get_expires_at_jalali(self, obj):
        return self.jalali_datetime(obj.expires_at)

    @admin.display(description='تاریخ ایجاد', ordering='created_at')
    def get_created_at_jalali(self, obj):
        return datetime2jalali(obj.created_at).strftime('%Y/%m/%d — %H:%M')
