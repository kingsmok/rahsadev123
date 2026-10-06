from django.contrib import admin
from . import models
from jalali_date import datetime2jalali, date2jalali
from jalali_date.admin import ModelAdminJalaliMixin


@admin.register(models.SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = ['site_name', 'site_slogan', 'phone1', 'email1', 'products_per_page']
    fieldsets = (
        ('هویت سایت', {
            'fields': ('site_name', 'site_slogan', 'logo', 'products_per_page')
        }),
        ('محتوای متنی', {
            'fields': ('text_about_us', 'text_contact_us', 'footer_description')
        }),
        ('اطلاعات تماس', {
            'fields': ('address', 'phone1', 'phone2', 'email1', 'email2')
        }),
        ('شبکه‌های اجتماعی', {
            'fields': ('instagram_link', 'telegram_link', 'whatsapp_link', 'twitter_link', 'youtube_link', 'linkedin_link')
        }),
        ('نمادهای اعتماد', {
            'fields': ('enamad_link', 'samandehi_link')
        }),
        ('سئو', {
            'fields': ('default_meta_title', 'default_meta_description')
        }),
        ('متن کپی رایت', {
            'fields': ('copy_right',)
        }),
    )


@admin.register(models.Banner)
class BannerAdmin(admin.ModelAdmin):
    list_display = ['title', 'banner_image', 'banner_type', 'status', 'get_created_at_jalali']
    list_filter = ['banner_type', 'status']
    list_editable = ['status']

    def short_title(self, obj):
        if len(obj.title) > 20:
            return obj.title[:20] + '...'
        return obj.title
    short_title.short_description = 'عنوان محصول'

    @admin.display(description='تاریخ ایجاد', ordering='created_at')
    def get_created_at_jalali(self, obj):
        return datetime2jalali(obj.created_at).strftime('%a, %d %b %Y')


@admin.register(models.ContactUs)
class ContactUsAdmin(ModelAdminJalaliMixin, admin.ModelAdmin):
    list_display = ['first_name', 'last_name', 'phone', 'short_message', 'get_date_send_jalali']

    def short_message(self, obj):
        if len(obj.message) > 20:
            return obj.message[:20] + '...'
        return obj.message
    short_message.short_description = 'متن پیام'

    @admin.display(description='تاریخ ارسال', ordering='date_send')
    def get_date_send_jalali(self, obj):
        return datetime2jalali(obj.date_send).strftime('%a, %d %b %Y')
