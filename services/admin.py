from django.contrib import admin
from .models import ServicePackage, PortfolioItem, ServiceRequest


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
class ServiceRequestAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'phone', 'package', 'project_type', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('full_name', 'phone', 'message')
    readonly_fields = ('created_at',)
    list_per_page = 30
