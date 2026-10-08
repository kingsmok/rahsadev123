from django.contrib import admin
from . import models
from core.admin_utils import EnhancedAdminMixin
from jalali_date import datetime2jalali
from jalali_date.admin import ModelAdminJalaliMixin


class OrderItemInline(admin.TabularInline):
    """اقلام سفارش فقط خواندنی است؛ تغییر دستی باعث ناهمخوانی مبالغ می‌شود."""
    model = models.OrderItem
    extra = 0
    can_delete = False
    fields = ['title_snapshot', 'unit_price', 'quantity', 'total_price']
    readonly_fields = ['title_snapshot', 'unit_price', 'quantity', 'total_price']
    show_change_link = True


@admin.register(models.Coupon)
class CouponAdmin(ModelAdminJalaliMixin, admin.ModelAdmin):
    list_display = ['code', 'discount_type', 'discount_value', 'max_usage', 'usage_count',
                    'get_valid_from_jalali', 'get_valid_to_jalali', 'is_active']
    list_editable = ['is_active']

    @admin.display(description='معتبر از', ordering='valid_from')
    def get_valid_from_jalali(self, obj):
        return datetime2jalali(obj.valid_from).strftime('%a, %d %b %Y')

    @admin.display(description='معتبر تا', ordering='valid_to')
    def get_valid_to_jalali(self, obj):
        return datetime2jalali(obj.valid_to).strftime('%a, %d %b %Y')


@admin.register(models.Cart)
class CartAdmin(ModelAdminJalaliMixin, admin.ModelAdmin):
    list_display = ['user', 'coupon', 'coupon_discount', 'get_created_at_jalali', 'get_updated_at_jalali']

    @admin.display(description='تاریخ ایجاد', ordering='created_at')
    def get_created_at_jalali(self, obj):
        return datetime2jalali(obj.created_at).strftime('%a, %d %b %Y')

    @admin.display(description='تاریخ به‌روزرسانی', ordering='updated_at')
    def get_updated_at_jalali(self, obj):
        return datetime2jalali(obj.updated_at).strftime('%a, %d %b %Y')


@admin.register(models.CartItem)
class CartItemAdmin(ModelAdminJalaliMixin, admin.ModelAdmin):
    list_display = ['cart', 'short_product_title', 'quantity', 'get_created_at_jalali']

    def short_product_title(self, obj):
        if len(obj.product.title) > 20:
            return obj.product.title[:20] + '...'
        return obj.product
    short_product_title.short_description = 'محصول'

    @admin.display(description='تاریخ ایجاد', ordering='created_at')
    def get_created_at_jalali(self, obj):
        return datetime2jalali(obj.created_at).strftime('%a, %d %b %Y')


@admin.register(models.OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('order', 'product', 'title_snapshot', 'unit_price', 'quantity', 'total_price')


@admin.register(models.Order)
class OrderAdmin(ModelAdminJalaliMixin, EnhancedAdminMixin, admin.ModelAdmin):
    list_display = ['order_number', 'user', 'items_summary', 'total_price', 'coupon_discount', 'shipping_cost',
                    'final_price', 'status', 'get_created_at_jalali']
    list_filter = ['status', 'created_at']
    search_fields = ['order_number', 'user__username', 'user__email', 'user__first_name', 'user__last_name']
    autocomplete_fields = ['user']
    date_hierarchy = 'created_at'
    list_select_related = ['user']
    readonly_fields = ['order_number', 'items_data', 'total_price', 'coupon_discount', 'shipping_cost',
                       'final_price', 'created_at', 'updated_at']
    inlines = [OrderItemInline]
    csv_filename = 'masaishop-orders.csv'
    fieldsets = (
        ('سفارش', {
            'fields': ('order_number', 'user', 'status', 'cart')
        }),
        ('مبالغ (خودکار از سبد خرید)', {
            'classes': ('collapse',),
            'fields': ('total_price', 'coupon_discount', 'shipping_cost', 'final_price', 'items_data')
        }),
        ('زمان‌ها', {
            'classes': ('collapse',),
            'fields': ('created_at', 'updated_at')
        }),
    )

    @admin.display(description='اقلام')
    def items_summary(self, obj):
        count = obj.order_items.count()
        return f'{count} قلم'

    @admin.display(description='تاریخ ایجاد', ordering='created_at')
    def get_created_at_jalali(self, obj):
        return datetime2jalali(obj.created_at).strftime('%Y/%m/%d — %H:%M')

    @admin.display(description='آخرین تغییر', ordering='updated_at')
    def get_updated_at_jalali(self, obj):
        return datetime2jalali(obj.updated_at).strftime('%Y/%m/%d — %H:%M')