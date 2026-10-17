from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.models import Group
from django.utils.html import format_html

from . import models
from .roles import AUTHOR_GROUP, VENDOR_GROUP, user_roles

from core.admin_utils import to_jalali
from jalali_date.admin import ModelAdminJalaliMixin


@admin.register(models.Profile)
class ProfileAdmin(ModelAdminJalaliMixin, admin.ModelAdmin):
    list_display = ['user', 'first_name', 'last_name', 'email', 'phone', 'get_masked_card_number', 'get_created_at_jalali']
    search_fields = ['user__username', 'email', 'phone']

    @admin.display(description='شماره کارت')
    def get_masked_card_number(self, obj):
        return obj.masked_card_number or '-'

    @admin.display(description='تاریخ ایجاد', ordering='created_at')
    def get_created_at_jalali(self, obj):
        return to_jalali(obj.created_at, '%a, %d %b %Y')


User = get_user_model()


class RoleListFilter(admin.SimpleListFilter):
    title = 'نقش'
    parameter_name = 'role'

    def lookups(self, request, model_admin):
        return (
            ('staff', 'مدیران'),
            ('vendor', 'فروشندگان'),
            ('author', 'نویسندگان'),
            ('customer', 'مشتریان'),
        )

    def queryset(self, request, queryset):
        value = self.value()
        if value == 'staff':
            return queryset.filter(is_staff=True)
        if value == 'vendor':
            return queryset.filter(groups__name=VENDOR_GROUP).distinct()
        if value == 'author':
            return queryset.filter(groups__name=AUTHOR_GROUP).distinct()
        if value == 'customer':
            return queryset.filter(is_staff=False).exclude(groups__name__in=[VENDOR_GROUP, AUTHOR_GROUP])
        return queryset


admin.site.unregister(User)


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    """کاربران با ستون «نقش» و اکشن‌های افزودن/حذف نقش فروشنده و نویسنده."""

    list_display = ('username', 'email', 'first_name', 'last_name', 'roles', 'is_active', 'date_joined')
    list_filter = (RoleListFilter, 'is_staff', 'is_superuser', 'is_active', 'groups')
    actions = ['make_vendor', 'remove_vendor', 'make_author', 'remove_author']

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('groups')

    @admin.display(description='نقش')
    def roles(self, obj):
        return format_html('<span class="fm-role">{}</span>', '، '.join(user_roles(obj)))

    def _change_group(self, request, queryset, group_name, add):
        group, _ = Group.objects.get_or_create(name=group_name)
        count = 0
        for user in queryset:
            if add:
                user.groups.add(group)
            else:
                user.groups.remove(group)
            count += 1
        verb = 'اضافه شد' if add else 'حذف شد'
        self.message_user(request, f'نقش «{group_name}» برای {count} کاربر {verb}.', messages.SUCCESS)

    @admin.action(description='دادن نقش فروشنده (قابل انتخاب در فیلد «فروشنده»ی محصول)')
    def make_vendor(self, request, queryset):
        self._change_group(request, queryset, VENDOR_GROUP, True)

    @admin.action(description='گرفتن نقش فروشنده')
    def remove_vendor(self, request, queryset):
        self._change_group(request, queryset, VENDOR_GROUP, False)

    @admin.action(description='دادن نقش نویسنده (قابل انتخاب در فیلد «نویسنده»ی مقاله)')
    def make_author(self, request, queryset):
        self._change_group(request, queryset, AUTHOR_GROUP, True)

    @admin.action(description='گرفتن نقش نویسنده')
    def remove_author(self, request, queryset):
        self._change_group(request, queryset, AUTHOR_GROUP, False)


@admin.register(models.PhoneOTP)
class PhoneOTPAdmin(admin.ModelAdmin):
    """گزارش ارسال کدهای پیامکی (خود کد ذخیره نمی‌شود)."""

    list_display = ('__str__', 'created_at', 'expires_at', 'attempts', 'consumed_at', 'ip_address')
    search_fields = ('phone',)
    exclude = ('code_hash',)
    readonly_fields = ('phone', 'created_at', 'expires_at', 'attempts', 'consumed_at', 'ip_address')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
