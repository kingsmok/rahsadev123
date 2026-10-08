from django.contrib import admin
from . import models
from jalali_date import datetime2jalali
from jalali_date.admin import ModelAdminJalaliMixin


class DigitalAssetInline(admin.StackedInline):
    model = models.DigitalAsset
    extra = 0


class ProductImageAdmin(admin.StackedInline):
    model = models.ProductImage


@admin.register(models.ProductCategory)
class ProductCategoryAdmin(ModelAdminJalaliMixin, admin.ModelAdmin):
    list_display = ['title', 'category_image', 'get_created_at_jalali']

    @admin.display(description='تاریخ ایجاد', ordering='created_at')
    def get_created_at_jalali(self, obj):
        return datetime2jalali(obj.created_at).strftime('%a, %d %b %Y')


@admin.register(models.ProductBrand)
class ProductBrandAdmin(ModelAdminJalaliMixin, admin.ModelAdmin):
    list_display = ['title', 'brand_image', 'views', 'get_created_at_jalali']

    @admin.display(description='تاریخ ایجاد', ordering='created_at')
    def get_created_at_jalali(self, obj):
        return datetime2jalali(obj.created_at).strftime('%a, %d %b %Y')


@admin.register(models.Product)
class ProductAdmin(ModelAdminJalaliMixin, admin.ModelAdmin):
    list_display = ['pid', 'vendor', 'short_title', 'product_type', 'license_type', 'old_price', 'price', 'stock_count', 'sales_count', 'views', 'status', 'product_image', 'get_created_at_jalali']
    prepopulated_fields = {'slug': ('title',)}
    list_editable = ['old_price', 'price', 'stock_count', 'status']
    list_filter = ['status', 'product_type', 'license_type', 'is_unlimited']
    search_fields = ['title', 'short_description', 'pid']
    inlines = [DigitalAssetInline, ProductImageAdmin]
    fieldsets = (
        ('اطلاعات اصلی', {
            'fields': ('vendor', 'title', 'slug', 'short_description', 'description', 'image', 'category', 'brand', 'status', 'is_featured', 'published_at')
        }),
        ('قیمت‌گذاری', {
            'fields': ('price', 'old_price', 'stock_count', 'is_unlimited')
        }),
        ('مشخصات محصول دیجیتال', {
            'fields': ('product_type', 'license_type', 'demo_url', 'documentation_url', 'requirements', 'operating_system', 'support_duration', 'update_duration')
        }),
        ('سئو', {
            'fields': ('meta_title', 'meta_description', 'canonical_url')
        }),
    )

    def short_title(self, obj):
        if len(obj.title) > 20:
            return obj.title[:20] + '...'
        return obj.title
    short_title.short_description = 'عنوان محصول'

    @admin.display(description='تاریخ ایجاد', ordering='created_at')
    def get_created_at_jalali(self, obj):
        return datetime2jalali(obj.created_at).strftime('%a, %d %b %Y')


@admin.register(models.ProductComment)
class ProductCommentAdmin(ModelAdminJalaliMixin, admin.ModelAdmin):
    list_display = ['short_product_title', 'author', 'short_body', 'status', 'get_created_at_jalali']
    list_editable = ['status']

    def short_product_title(self, obj):
        if len(obj.product.title) > 10:
            return obj.product.title[:10] + '...'
        return obj.product
    short_product_title.short_description = 'محصول مربوطه'

    def short_body(self, obj):
        if len(obj.body) > 20:
            return obj.body[:20] + '...'
        return obj.body
    short_body.short_description = 'متن دیدگاه'

    @admin.display(description='تاریخ ایجاد', ordering='created_at')
    def get_created_at_jalali(self, obj):
        return datetime2jalali(obj.created_at).strftime('%a, %d %b %Y')

