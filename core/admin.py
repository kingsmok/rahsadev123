from django import forms
from django.contrib import admin, messages
from django.contrib.admin.options import IS_POPUP_VAR
from django.contrib.admin.utils import unquote
from django.db.models import Subquery
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.html import format_html
from . import models
from .admin_utils import EnhancedAdminMixin
from jalali_date import datetime2jalali

from core.admin_code import CodeEditorWidget
from core.admin_utils import to_jalali
from core.custom_html import can_edit_raw_html
from core.branding import DEFAULT_SITE_NAME, NAME_BEARING_FIELDS, Brand, replace_name
from jalali_date.admin import ModelAdminJalaliMixin


class SiteSettingsForm(forms.ModelForm):
    replace_old_name = forms.BooleanField(
        required=False,
        initial=True,
        label='جایگزینی نام قبلی در متن‌ها',
        help_text='با ذخیره، هر جا نام قبلی سایت (یا نام پیش‌فرض «%s») در شعار، عنوان و توضیحات سئو، '
                  'متن فوتر، کپی‌رایت و متن‌های درباره/تماس آمده باشد با «نام سایت» جدید جایگزین '
                  'می‌شود. اگر نام قبلی را عمداً در این متن‌ها نوشته‌اید، تیک را بردارید.' % DEFAULT_SITE_NAME,
    )

    class Meta:
        model = models.SiteSettings
        fields = '__all__'


@admin.register(models.SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    """تنظیمات سایت؛ فقط یک ردیف دارد و همهٔ بخش‌ها از همان ردیف می‌خوانند.

    قبلاً دکمهٔ «افزودن» ردیف دوم می‌ساخت که سایت هرگز آن را نمی‌خواند
    (``SiteSettings.objects.first()``)؛ نام و لوگوی واردشده در آن ردیف هیچ‌جا
    نمایش داده نمی‌شد.
    """

    form = SiteSettingsForm
    list_display = ['site_name', 'is_active_row', 'site_slogan', 'phone1', 'email1', 'products_per_page']
    readonly_fields = ['brand_preview']
    fieldsets = (
        ('هویت سایت', {
            'description': 'نام، لوگو و آیکن تب این بخش در همهٔ قسمت‌ها اعمال می‌شود: فروشگاه، پنل کاربری، '
                           'Django Admin، پنل مدیریت، صفحهٔ آفلاین، نصب اپ (PWA) و ایمیل‌ها.',
            'fields': ('site_name', 'replace_old_name', 'site_slogan', 'logo', 'favicon', 'brand_preview',
                       'products_per_page')
        }),
        ('محتوای متنی', {
            'fields': ('text_about_us', 'text_contact_us', 'footer_description')
        }),
        ('اطلاعات تماس', {
            'fields': ('address', 'phone1', 'phone2', 'email1', 'email2')
        }),
        ('شبکه‌های اجتماعی', {
            'description': 'هر شبکه‌ای که لینکش پر شود در فوتر، صفحهٔ تماس و منوی موبایل با آیکن خودش نمایش داده می‌شود. '
                           'می‌توانید آدرس کامل (https://…) یا شناسه با @ وارد کنید.',
            'fields': ('instagram_link', 'telegram_link', 'whatsapp_link', 'twitter_link', 'youtube_link', 'linkedin_link',
                       'facebook_link', 'pinterest_link', 'github_link')
        }),
        ('شبکه‌های اجتماعی و پیام‌رسان‌های ایرانی', {
            'fields': ('aparat_link', 'eitaa_link', 'rubika_link', 'bale_link', 'soroush_link', 'igap_link', 'virgool_link')
        }),
        ('نمادهای اعتماد', {
            'fields': ('enamad_link', 'samandehi_link')
        }),
        ('سئو', {
            'fields': ('default_meta_title', 'default_meta_description', 'google_site_verification', 'bing_site_verification')
        }),
        ('متن کپی رایت', {
            'fields': ('copy_right',)
        }),
    )

    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        if obj is not None and not self.has_change_permission(request, obj):
            # View-only staff cannot save, so the replace option would only render as «None».
            fieldsets = [
                (title, {**options, 'fields': tuple(name for name in options['fields'] if name != 'replace_old_name')})
                for title, options in fieldsets
            ]
        return fieldsets

    def get_queryset(self, request):
        active_pk = models.SiteSettings.objects.order_by('pk').values('pk')[:1]
        return super().get_queryset(request).annotate(active_pk=Subquery(active_pk))

    @admin.display(boolean=True, description='در حال استفاده روی سایت')
    def is_active_row(self, obj):
        return obj.pk == getattr(obj, 'active_pk', None)

    def has_add_permission(self, request):
        # A second row would be silently ignored by every page.
        return super().has_add_permission(request) and not models.SiteSettings.objects.exists()

    def changelist_view(self, request, extra_context=None):
        pks = list(models.SiteSettings.objects.order_by('pk').values_list('pk', flat=True)[:2])
        if len(pks) == 1 and IS_POPUP_VAR not in request.GET and self.has_view_or_change_permission(request):
            # One settings row: open it directly instead of a one-line list.
            return redirect(reverse('admin:core_sitesettings_change', args=[pks[0]]))
        if len(pks) > 1:
            messages.warning(
                request,
                f'بیش از یک ردیف تنظیمات وجود دارد، اما سایت فقط ردیف شمارهٔ {pks[0]} (ستون «در حال استفاده») '
                f'را می‌خواند و بقیه هیچ‌جا اعمال نمی‌شوند. نام و لوگوی دلخواه را در همان ردیف وارد کنید '
                f'و ردیف‌های اضافه را حذف کنید.',
            )
        return super().changelist_view(request, extra_context)

    def change_view(self, request, object_id, form_url='', extra_context=None):
        if request.method == 'GET':
            obj = self.get_object(request, unquote(object_id))
            if obj is not None and self.has_change_permission(request, obj):
                self._warn_about_stale_names(request, obj)
        return super().change_view(request, object_id, form_url, extra_context)

    @staticmethod
    def _field_label(field_name):
        return str(models.SiteSettings._meta.get_field(field_name).verbose_name)

    def _warn_about_stale_names(self, request, obj):
        name = (obj.site_name or '').strip()
        if not name or name == DEFAULT_SITE_NAME:
            return
        stale = [
            self._field_label(field_name) for field_name in NAME_BEARING_FIELDS
            if replace_name(getattr(obj, field_name) or '', DEFAULT_SITE_NAME, name) != (getattr(obj, field_name) or '')
        ]
        if stale:
            messages.warning(
                request,
                f'نام قبلی «{DEFAULT_SITE_NAME}» هنوز در این بخش‌ها آمده و روی سایت نمایش داده می‌شود: '
                f'{"، ".join(stale)}. با ذخیرهٔ همین فرم (گزینهٔ «جایگزینی نام قبلی در متن‌ها» روشن) '
                f'با «{name}» جایگزین می‌شود.',
            )

    def save_model(self, request, obj, form, change):
        replaced, too_long = [], []
        if form.cleaned_data.get('replace_old_name'):
            new_name = (obj.site_name or '').strip()
            previous = (form.initial.get('site_name') or '').strip() if change else ''
            # Longest first, so «فایل‌مارکت پلاس» is not half-replaced via «فایل‌مارکت».
            old_names = sorted(
                {candidate for candidate in (previous, DEFAULT_SITE_NAME) if candidate and candidate != new_name},
                key=len, reverse=True,
            )
            for field_name in NAME_BEARING_FIELDS:
                current = getattr(obj, field_name) or ''
                updated = current
                for old_name in old_names:
                    updated = replace_name(updated, old_name, new_name)
                if updated == current:
                    continue
                max_length = obj._meta.get_field(field_name).max_length
                if max_length and len(updated) > max_length:
                    too_long.append(self._field_label(field_name))
                    continue
                setattr(obj, field_name, updated)
                replaced.append(self._field_label(field_name))
        super().save_model(request, obj, form, change)
        if replaced:
            messages.info(request, f'نام سایت در این بخش‌ها هم به «{obj.site_name}» تغییر کرد: {"، ".join(replaced)}.')
        if too_long:
            messages.warning(
                request,
                f'این بخش‌ها هنوز نام قبلی را دارند، چون با نام جدید از حداکثر طول مجاز بلندتر می‌شدند؛ '
                f'لطفاً دستی کوتاه کنید: {"، ".join(too_long)}.',
            )

    @admin.display(description='پیش‌نمایش آیکن تب و لوگو')
    def brand_preview(self, obj):
        if obj is None or not obj.pk:
            return 'پس از ذخیره نمایش داده می‌شود.'
        if obj.pk != getattr(obj, 'active_pk', obj.pk):
            return 'این ردیف روی سایت استفاده نمی‌شود؛ فقط ردیف «در حال استفاده» اعمال می‌شود.'
        brand = Brand(obj)
        if brand.has_favicon:
            source = 'از «آیکن تب مرورگر» آپلودشده'
        elif brand.has_custom_icon:
            source = 'از لوگو ساخته شده (برای نتیجهٔ بهتر یک تصویر مربعی در «آیکن تب مرورگر» آپلود کنید)'
        else:
            source = 'آیکن پیش‌فرض (هنوز لوگو یا آیکنی آپلود نشده است)'
        box = 'vertical-align:middle;border:1px solid var(--hairline-color,#ddd);border-radius:6px;background:#fff'
        logo = (
            format_html('<img src="{}" alt="لوگوی فعلی" style="{};max-height:56px;max-width:220px;padding:4px">',
                        brand.logo_url, box)
            if brand.logo_url else format_html('<span>{}</span>', 'لوگوی متنی «%s»' % brand.name)
        )
        return format_html(
            '<div style="display:flex;flex-wrap:wrap;gap:18px;align-items:center">'
            '<span>تب مرورگر: <img src="{}" alt="" width="16" height="16" style="{}"> '
            '<img src="{}" alt="" width="32" height="32" style="{}"></span>'
            '<span>آیفون / نصب اپ: <img src="{}" alt="" width="60" height="60" style="{}"></span>'
            '<span>لوگو: {}</span></div>'
            '<div class="help" style="margin-top:6px">منبع آیکن: {}</div>',
            brand.favicon_url, box, brand.favicon_url, box, brand.touch_icon_url, box, logo, source,
        )


class BannerAdminForm(forms.ModelForm):
    class Meta:
        model = models.Banner
        fields = '__all__'
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }


@admin.register(models.Banner)
class BannerAdmin(admin.ModelAdmin):
    form = BannerAdminForm
    list_display = ['title', 'banner_image', 'banner_type', 'display_size', 'width', 'order', 'status', 'get_created_at_jalali']
    list_filter = ['banner_type', 'status', 'display_size']
    list_editable = ['order', 'status']
    search_fields = ['title', 'subtitle', 'description']
    readonly_fields = ['preview']
    fieldsets = (
        (None, {'fields': ('title', 'banner_type', 'status', 'order')}),
        ('تصویر و لینک', {
            'description': 'اندازهٔ پیشنهادی: اسلایدر ۱۹۲۰×۶۰۰، بنر بزرگ ۸۰۰×۳۰۰، بنر کوچک ۴۰۰×۲۵۰ و بنر تک ۱۶۰۰×۲۵۰ پیکسل.',
            'fields': ('image', 'mobile_image', 'url', 'open_in_new_tab', 'preview'),
        }),
        ('اندازهٔ نمایش', {'fields': ('display_size', 'width')}),
        ('متن روی بنر', {
            'fields': ('show_text', 'subtitle', 'description', 'button_text', 'text_position', 'text_theme'),
        }),
    )

    @admin.display(description='پیش‌نمایش')
    def preview(self, obj):
        if not obj or not obj.image:
            return 'پس از ذخیره، پیش‌نمایش تصویر نمایش داده می‌شود.'
        return format_html('<img src="{}" alt="" style="max-width:420px;max-height:180px;border-radius:10px;object-fit:cover">',
                           obj.image.url)

    @admin.display(description='تاریخ ایجاد', ordering='created_at')
    def get_created_at_jalali(self, obj):
        return to_jalali(obj.created_at, '%a, %d %b %Y')


class HtmlBlockAdminForm(forms.ModelForm):
    class Meta:
        model = models.HtmlBlock
        fields = '__all__'
        widgets = {'html': CodeEditorWidget()}


@admin.register(models.HtmlBlock)
class HtmlBlockAdmin(admin.ModelAdmin):
    """بلوک‌های کد HTML؛ فقط برای مدیر کل یا دارندهٔ مجوز «ویرایش کد HTML خام»."""

    form = HtmlBlockAdminForm
    list_display = ['title', 'placement', 'is_active', 'order', 'full_width', 'updated_at']
    list_filter = ['placement', 'is_active']
    list_editable = ['is_active', 'order']
    search_fields = ['title', 'html']
    fieldsets = (
        (None, {'fields': ('title', 'placement', 'is_active', 'order', 'full_width')}),
        ('کد HTML (با پیش‌نمایش زنده)', {'fields': ('html',)}),
    )

    def has_add_permission(self, request):
        return can_edit_raw_html(request.user) and super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        return can_edit_raw_html(request.user) and super().has_change_permission(request, obj)


@admin.register(models.ContactUs)
class ContactUsAdmin(EnhancedAdminMixin, ModelAdminJalaliMixin, admin.ModelAdmin):
    list_display = ['first_name', 'last_name', 'phone', 'short_message', 'get_date_send_jalali']
    search_fields = ['first_name', 'last_name', 'phone', 'message']
    date_hierarchy = 'date_send'
    csv_filename = 'masaishop-messages.csv'

    def short_message(self, obj):
        if len(obj.message) > 20:
            return obj.message[:20] + '...'
        return obj.message
    short_message.short_description = 'متن پیام'

    @admin.display(description='تاریخ ارسال', ordering='date_send')
    def get_date_send_jalali(self, obj):
        return datetime2jalali(obj.date_send).strftime('%Y/%m/%d — %H:%M')


@admin.register(models.Redirect)
class RedirectAdmin(admin.ModelAdmin):
    list_display = ['old_path', 'new_path', 'status_code', 'is_active', 'hits', 'note', 'get_updated_jalali']
    list_editable = ['status_code', 'is_active']
    list_filter = ['status_code', 'is_active']
    search_fields = ['old_path', 'new_path', 'note']
    list_per_page = 50

    @admin.display(description='آخرین استفاده', ordering='updated_at')
    def get_updated_jalali(self, obj):
        return datetime2jalali(obj.updated_at).strftime('%Y/%m/%d - %H:%M')


@admin.register(models.NewsletterSubscriber)
class NewsletterSubscriberAdmin(EnhancedAdminMixin, admin.ModelAdmin):
    list_display = ['email', 'is_active', 'get_joined_jalali']
    list_filter = ['is_active', 'created_at']
    search_fields = ['email']
    list_editable = ['is_active']
    date_hierarchy = 'created_at'
    csv_filename = 'masaishop-newsletter.csv'

    @admin.display(description='تاریخ عضویت', ordering='created_at')
    def get_joined_jalali(self, obj):
        return datetime2jalali(obj.created_at).strftime('%Y/%m/%d — %H:%M')
