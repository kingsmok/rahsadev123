from django.contrib import admin
from .models import ServicePackage, PortfolioItem, ServiceRequest

from core.admin_utils import EnhancedAdminMixin
from jalali_date import datetime2jalali


@admin.register(ServicePackage)
class ServicePackageAdmin(admin.ModelAdmin):
    list_display = ('title', 'price', 'delivery_days', 'is_featured', 'is_active', 'order')
    list_editable = ('is_featured', 'is_active', 'order')
    search_fields = ('title',)
    prepopulated_fields = {}


@admin.register(PortfolioItem)
class PortfolioItemAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'url', 'is_active', 'order')
    list_editable = ('is_active', 'order')
    list_filter = ('category',)
    search_fields = ('title',)


@admin.register(ServiceRequest)
class ServiceRequestAdmin(EnhancedAdminMixin, admin.ModelAdmin):
    list_display = ('full_name', 'phone', 'package', 'project_type', 'status', 'get_created_at_jalali')
    list_filter = ('status', 'package', 'created_at')
    search_fields = ('full_name', 'phone', 'email', 'message', 'project_type')
    readonly_fields = ('created_at',)
    date_hierarchy = 'created_at'
    list_select_related = ('package',)
    list_per_page = 30
    csv_filename = 'masaishop-service-requests.csv'
    actions = ['mark_contacted', 'mark_done', 'export_selected_as_csv']
    fieldsets = (
        ('مشتری', {
            'fields': ('full_name', 'phone', 'email')
        }),
        ('درخواست', {
            'fields': ('package', 'project_type', 'budget', 'message', 'status')
        }),
        ('زمان', {
            'classes': ('collapse',),
            'fields': ('created_at',)
        }),
    )

    @admin.action(description='ثبت تماس گرفته‌شده')
    def mark_contacted(self, request, queryset):
        updated = queryset.update(status='contacted')
        self.message_user(request, f'{updated} درخواست به «تماس گرفته شد» تغییر کرد.')

    @admin.action(description='پایان‌یافته کردن درخواست‌ها')
    def mark_done(self, request, queryset):
        updated = queryset.update(status='done')
        self.message_user(request, f'{updated} درخواست پایان‌یافته شد.')

    @admin.display(description='تاریخ درخواست', ordering='created_at')
    def get_created_at_jalali(self, obj):
        return datetime2jalali(obj.created_at).strftime('%Y/%m/%d — %H:%M')
