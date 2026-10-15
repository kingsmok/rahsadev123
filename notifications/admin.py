import logging

from django import forms
from django.contrib import admin, messages
from django.core.mail import EmailMessage
from django.http import HttpResponseNotAllowed, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.http import url_has_allowed_host_and_scheme

from core.admin_utils import to_jalali

from .email_backend import smtp_backend_from_settings
from .models import AdminNotification, EmailSettings, SmsSettings

logger = logging.getLogger(__name__)


@admin.register(AdminNotification)
class AdminNotificationAdmin(admin.ModelAdmin):
    list_display = ['status_icon', 'title', 'kind', 'level', 'get_created_jalali', 'channels', 'open_link']
    list_display_links = ['title']
    list_filter = ['is_read', 'kind', 'level']
    search_fields = ['title', 'message']
    readonly_fields = ['kind', 'level', 'title', 'message', 'url', 'is_read', 'read_at', 'read_by',
                       'emailed', 'sms_sent', 'created_at']
    exclude = ['dedupe_key']
    actions = ['mark_read', 'mark_unread']
    list_per_page = 50

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        # Read-only detail page; reading happens through «open» and the actions.
        return False

    @admin.display(description='')
    def status_icon(self, obj):
        return format_html(
            '<span class="fm-notif-dot fm-notif-dot--{}" title="{}"><i class="fa-solid {}" aria-hidden="true"></i></span>',
            obj.level, 'خوانده‌نشده' if not obj.is_read else 'خوانده شده', obj.icon,
        )

    @admin.display(description='زمان', ordering='created_at')
    def get_created_jalali(self, obj):
        return to_jalali(obj.created_at)

    @admin.display(description='ارسال')
    def channels(self, obj):
        parts = []
        if obj.emailed:
            parts.append('ایمیل')
        if obj.sms_sent:
            parts.append('پیامک')
        return '، '.join(parts) or '—'

    @admin.display(description='بررسی')
    def open_link(self, obj):
        if not obj.url:
            return '—'
        return format_html('<a class="button" href="{}">بررسی</a>',
                           reverse('admin:notifications_adminnotification_open', args=[obj.pk]))

    @admin.action(description='علامت‌گذاری به عنوان خوانده شده')
    def mark_read(self, request, queryset):
        updated = queryset.filter(is_read=False).update(is_read=True, read_at=timezone.now(), read_by=request.user)
        self.message_user(request, f'{updated} اعلان خوانده شد.', messages.SUCCESS)

    @admin.action(description='علامت‌گذاری به عنوان خوانده‌نشده')
    def mark_unread(self, request, queryset):
        updated = queryset.update(is_read=False, read_at=None, read_by=None)
        self.message_user(request, f'{updated} اعلان خوانده‌نشده شد.', messages.SUCCESS)

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path('feed/', self.admin_site.admin_view(self.feed_view), name='notifications_adminnotification_feed'),
            path('mark-all-read/', self.admin_site.admin_view(self.mark_all_read_view),
                 name='notifications_adminnotification_mark_all_read'),
            path('<int:pk>/open/', self.admin_site.admin_view(self.open_view),
                 name='notifications_adminnotification_open'),
        ]
        return custom + urls

    def feed_view(self, request):
        if not self.has_view_permission(request):
            return JsonResponse({'detail': 'forbidden'}, status=403)
        items = [
            {
                'id': item.pk,
                'title': item.title,
                'kind': item.get_kind_display(),
                'level': item.level,
                'icon': item.icon,
                'is_read': item.is_read,
                'created': to_jalali(item.created_at, '%Y/%m/%d %H:%M'),
                'open_url': reverse('admin:notifications_adminnotification_open', args=[item.pk]),
            }
            for item in AdminNotification.objects.all()[:8]
        ]
        response = JsonResponse({
            'unread': AdminNotification.objects.filter(is_read=False).count(),
            'latest_id': items[0]['id'] if items else 0,
            'items': items,
        })
        response['Cache-Control'] = 'no-store'
        return response

    def mark_all_read_view(self, request):
        if request.method != 'POST':
            return HttpResponseNotAllowed(['POST'])
        if not self.has_view_permission(request):
            return redirect('admin:index')
        updated = AdminNotification.objects.filter(is_read=False).update(
            is_read=True, read_at=timezone.now(), read_by=request.user)
        self.message_user(request, f'{updated} اعلان خوانده شد.', messages.SUCCESS)
        target = request.META.get('HTTP_REFERER', '')
        if not url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()},
                                               require_https=request.is_secure()):
            target = reverse('admin:notifications_adminnotification_changelist')
        return HttpResponseRedirect(target)

    def open_view(self, request, pk):
        notification = get_object_or_404(AdminNotification, pk=pk)
        if not self.has_view_permission(request, notification):
            return redirect('admin:index')
        notification.mark_read(request.user)
        target = notification.url
        if not (target and target.startswith('/') and not target.startswith('//')):
            target = reverse('admin:notifications_adminnotification_change', args=[notification.pk])
        return HttpResponseRedirect(target)


class _SecretField(forms.CharField):
    """A password-like input that never echoes the stored value back."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('required', False)
        kwargs.setdefault('widget', forms.PasswordInput(render_value=False, attrs={'autocomplete': 'new-password'}))
        super().__init__(*args, **kwargs)


class _SingletonAdmin(admin.ModelAdmin):
    secret_fields = ()

    def has_add_permission(self, request):
        return not self.model.objects.exists() and super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        obj = self.model.load()
        return redirect(reverse(f'admin:{obj._meta.app_label}_{obj._meta.model_name}_change', args=[obj.pk]))

    def save_model(self, request, obj, form, change):
        # An empty secret field keeps the stored value; the clear checkbox removes it.
        for name in self.secret_fields:
            if form.cleaned_data.get(f'clear_{name}'):
                setattr(obj, name, '')
            elif not form.cleaned_data.get(name):
                stored = self.model.objects.filter(pk=obj.pk).values_list(name, flat=True).first()
                setattr(obj, name, stored or '')
        super().save_model(request, obj, form, change)


class EmailSettingsForm(forms.ModelForm):
    password = _SecretField(label='رمز عبور ایمیل',
                            help_text='برای تغییر، رمز جدید را وارد کنید. خالی گذاشتن = حفظ رمز فعلی.')
    clear_password = forms.BooleanField(required=False, label='حذف رمز ذخیره‌شده')
    test_recipient = forms.EmailField(required=False, label='ارسال ایمیل آزمایشی به',
                                      help_text='پس از ذخیره، یک ایمیل آزمایشی با همین تنظیمات به این آدرس فرستاده می‌شود.')

    class Meta:
        model = EmailSettings
        fields = '__all__'


@admin.register(EmailSettings)
class EmailSettingsAdmin(_SingletonAdmin):
    form = EmailSettingsForm
    secret_fields = ('password',)
    readonly_fields = ['password_status', 'updated_at']
    fieldsets = (
        ('اتصال به ایمیل هاست (SMTP)', {
            'description': 'اطلاعات را از پنل هاست (cPanel/DirectAdmin ← Email Accounts ← Connect Devices) بردارید.',
            'fields': ('is_enabled', 'host', 'port', 'security', 'username', 'password', 'password_status',
                       'clear_password', 'from_email', 'from_name', 'timeout'),
        }),
        ('اعلان‌های ایمیلی مدیر', {
            'fields': ('admin_recipients', 'notify_order_paid', 'notify_service_request', 'notify_contact',
                       'notify_comment'),
        }),
        ('آزمایش', {'fields': ('test_recipient', 'updated_at')}),
    )

    @admin.display(description='وضعیت رمز')
    def password_status(self, obj):
        return 'تنظیم شده' if obj and obj.password else 'تنظیم نشده'

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        recipient = form.cleaned_data.get('test_recipient')
        if recipient:
            self._send_test(request, obj, recipient)

    def _send_test(self, request, config, recipient):
        if not config.host:
            self.message_user(request, 'برای ارسال آزمایشی ابتدا آدرس سرور SMTP را وارد کنید.', messages.WARNING)
            return
        from core.branding import get_brand

        site_name = get_brand(request).name
        try:
            connection = smtp_backend_from_settings(config)
            EmailMessage(
                f'ایمیل آزمایشی {site_name}',
                'اتصال ایمیل هاست با موفقیت برقرار شد. این پیام از بخش «تنظیمات ایمیل (SMTP)» فرستاده شده است.',
                config.sender or None, [recipient], connection=connection,
            ).send(fail_silently=False)
        except Exception as exc:  # SMTP errors are many; show their text to the admin.
            logger.warning('SMTP test failed: %s', exc)
            self.message_user(request, f'ارسال ایمیل آزمایشی ناموفق بود: {exc}', messages.ERROR)
        else:
            if not config.is_enabled:
                self.message_user(request, 'ایمیل آزمایشی ارسال شد. برای استفاده در سایت، گزینهٔ «استفاده از این تنظیمات SMTP» را فعال کنید.', messages.WARNING)
            else:
                self.message_user(request, f'ایمیل آزمایشی به {recipient} ارسال شد.', messages.SUCCESS)


class SmsSettingsForm(forms.ModelForm):
    api_key = _SecretField(label='کلید API (X-API-KEY)',
                           help_text='برای تغییر، کلید جدید را وارد کنید. خالی گذاشتن = حفظ کلید فعلی.')
    clear_api_key = forms.BooleanField(required=False, label='حذف کلید ذخیره‌شده')
    test_mobile = forms.CharField(required=False, label='ارسال کد آزمایشی به موبایل',
                                  help_text='پس از ذخیره، یک کد آزمایشی با قالب کد تأیید به این شماره فرستاده می‌شود.')

    class Meta:
        model = SmsSettings
        fields = '__all__'

    def clean_test_mobile(self):
        from .sms import normalize_mobile

        value = self.cleaned_data.get('test_mobile')
        if value and not normalize_mobile(value):
            raise forms.ValidationError('شماره موبایل معتبر نیست.')
        return normalize_mobile(value) if value else ''


@admin.register(SmsSettings)
class SmsSettingsAdmin(_SingletonAdmin):
    form = SmsSettingsForm
    secret_fields = ('api_key',)
    readonly_fields = ['api_key_status', 'updated_at']
    fieldsets = (
        ('اتصال به sms.ir', {
            'fields': ('is_enabled', 'api_key', 'api_key_status', 'clear_api_key', 'line_number'),
        }),
        ('ورود و ثبت‌نام با کد پیامکی', {
            'fields': ('otp_login_enabled', 'otp_template_id', 'otp_parameter', 'otp_length', 'otp_ttl_seconds'),
        }),
        ('پیامک اعلان به مدیران', {
            'fields': ('admin_mobiles', 'alert_template_id', 'notify_order_paid', 'notify_service_request',
                       'notify_contact', 'notify_comment'),
        }),
        ('پیامک به مشتری', {'fields': ('customer_order_template_id',)}),
        ('آزمایش', {'fields': ('test_mobile', 'updated_at')}),
    )

    @admin.display(description='وضعیت کلید')
    def api_key_status(self, obj):
        return 'تنظیم شده' if obj and obj.api_key else 'تنظیم نشده'

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        mobile = form.cleaned_data.get('test_mobile')
        if mobile:
            self._send_test(request, obj, mobile)

    def _send_test(self, request, config, mobile):
        from .sms import SmsError, SmsIrClient

        if not (config.api_key and config.otp_template_id):
            self.message_user(request, 'برای ارسال آزمایشی، کلید API و شناسه قالب کد تأیید را وارد کنید.', messages.WARNING)
            return
        try:
            SmsIrClient(config.api_key).send_verify(mobile, config.otp_template_id, {config.otp_parameter: '12345'})
        except SmsError as exc:
            self.message_user(request, f'ارسال پیامک آزمایشی ناموفق بود: {exc}', messages.ERROR)
        else:
            self.message_user(request, f'پیامک آزمایشی (کد 12345) به {mobile} ارسال شد.', messages.SUCCESS)
