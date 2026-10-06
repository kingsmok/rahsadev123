from django.contrib import admin
from . import models
from jalali_date import datetime2jalali, date2jalali
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
        return datetime2jalali(obj.created_at).strftime('%a, %d %b %Y')
