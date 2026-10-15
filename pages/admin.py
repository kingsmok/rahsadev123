from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from core.admin_code import RawHtmlAdminMixin

from .models import StaticPage


@admin.register(StaticPage)
class StaticPageAdmin(RawHtmlAdminMixin, admin.ModelAdmin):
    list_display = ('title', 'slug', 'layout', 'is_published', 'updated_at', 'view_link')
    list_filter = ('is_published', 'layout')
    search_fields = ('title', 'slug', 'summary')
    prepopulated_fields = {'slug': ('title',)}
    readonly_fields = ('view_link',)
    fieldsets = (
        (None, {'fields': ('title', 'slug', 'summary', 'is_published', 'view_link')}),
        ('چیدمان صفحه', {
            'description': 'نوع چیدمان صفحه را انتخاب کنید. برای صفحه‌ای که کاملاً با کد HTML ساخته می‌شود، «لندینگ» '
                           'و حالت «جایگزین کامل محتوا» را انتخاب کنید.',
            'fields': ('layout', 'show_page_head'),
        }),
        ('محتوا (ویرایشگر متنی)', {'fields': ('content',)}),
        ('کد HTML سفارشی (با پیش‌نمایش زنده)', {
            'description': 'HTML، CSS (تگ style) و JS (تگ script) که عیناً در صفحه اجرا می‌شود. '
                           'فقط مدیر کل یا دارندهٔ مجوز «ویرایش کد HTML خام» می‌تواند آن را تغییر دهد.',
            'fields': ('custom_html_mode', 'custom_html'),
        }),
    )

    @admin.display(description='مشاهده در سایت')
    def view_link(self, obj):
        if not obj or not obj.pk:
            return '—'
        label = 'مشاهدهٔ صفحه' if obj.is_published else 'پیش‌نمایش (منتشر نشده)'
        return format_html('<a href="{}" target="_blank" rel="noopener">{}</a>',
                           reverse('pages:detail', args=[obj.slug]), label)
