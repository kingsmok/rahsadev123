from django.contrib import admin
from .models import DownloadToken


@admin.register(DownloadToken)
class DownloadTokenAdmin(admin.ModelAdmin):
    list_display = ('product', 'user', 'order', 'download_count', 'max_downloads', 'is_active', 'expires_at', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('token', 'user__username', 'product__title', 'order__order_number')
    readonly_fields = ('token', 'download_count', 'created_at')
