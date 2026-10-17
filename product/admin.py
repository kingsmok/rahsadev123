from django import forms
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.utils.html import format_html

from . import models
from accounts.roles import vendor_choices
from core.admin_code import RawHtmlAdminMixin
from core.admin_utils import EnhancedAdminMixin, to_jalali
from jalali_date.admin import ModelAdminJalaliMixin


class DigitalAssetForm(forms.ModelForm):
    """«آپلود فایل» یا «لینک دانلود»؛ فقط فیلدهای همان حالت نمایش داده می‌شوند (fm-digital-asset.js)."""

    link_size_mb = forms.DecimalField(
        label='حجم فایل (مگابایت)', required=False, min_value=0, max_digits=12, decimal_places=2,
        help_text='اختیاری، برای حالت «لینک دانلود»: برای نمایش حجم در صفحهٔ محصول و «دانلودهای من». '
                  'حجم فایل آپلودشده خودکار محاسبه می‌شود.',
    )

    class Meta:
        model = models.DigitalAsset
        fields = ('source', 'file', 'external_url', 'link_size_mb', 'file_type', 'version', 'changelog', 'preview_file')
        widgets = {
            'source': forms.RadioSelect(attrs={'class': 'fm-asset-source'}),
            'external_url': forms.URLInput(attrs={'dir': 'ltr', 'placeholder': 'https://dl.example.com/files/product.zip',
                                                  'style': 'width: 100%; max-width: 560px'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        instance = self.instance
        if instance.pk and instance.is_link and instance.file_size:
            self.initial.setdefault('link_size_mb', round(instance.file_size / (1024 * 1024), 2))

    def save(self, commit=True):
        asset = super().save(commit=False)
        if asset.is_link:
            size_mb = self.cleaned_data.get('link_size_mb')
            asset.file_size = int(size_mb * 1024 * 1024) if size_mb else 0
        if commit:
            asset.save()
            self.save_m2m()
        return asset


class DigitalAssetInline(admin.StackedInline):
    model = models.DigitalAsset
    form = DigitalAssetForm
    # فرم از همان ابتدا دیده شود؛ محصول بدون فایل هم قابل ذخیره است (فرم خالی نادیده گرفته می‌شود).
    extra = 1
    max_num = 1
    can_delete = True
    verbose_name = 'فایل محصول (آپلود یا لینک دانلود)'
    verbose_name_plural = 'فایل محصول (آپلود یا لینک دانلود)'
    readonly_fields = ('delivery_status',)
    fieldsets = (
        (None, {'fields': ('source', 'file', 'external_url', 'link_size_mb', 'delivery_status')}),
        ('مشخصات فایل', {'fields': ('file_type', 'version', 'changelog', 'preview_file')}),
    )

    @property
    def media(self):
        from core.assets import asset_url

        return super().media + forms.Media(js=(asset_url('js/fm-digital-asset.js'),))

    @admin.display(description='وضعیت تحویل')
    def delivery_status(self, obj):
        if not obj or not obj.pk:
            return 'پس از ذخیره نمایش داده می‌شود.'
        if obj.is_deliverable():
            label = 'لینک دانلود تنظیم شده است' if obj.is_link else 'فایل روی سایت موجود است'
            return format_html('<span class="fm-status fm-status--ok">✓ {}</span> — {} دانلود تا کنون',
                               label, obj.download_count)
        return format_html('<span class="fm-status fm-status--bad">✗ {}</span>',
                           'فایل در دسترس نیست؛ دوباره آپلود کنید یا لینک را بررسی کنید.')


class ProductImageAdmin(admin.StackedInline):
    model = models.ProductImage


@admin.register(models.ProductCategory)
class ProductCategoryAdmin(ModelAdminJalaliMixin, admin.ModelAdmin):
    list_display = ['title', 'category_image', 'icon', 'show_in_menu', 'menu_order', 'get_created_at_jalali']
    list_editable = ['show_in_menu', 'menu_order']
    # برای autocomplete در فرم محصول
    search_fields = ['title']
    prepopulated_fields = {'slug': ('title',)}
    fieldsets = (
        (None, {'fields': ('title', 'slug', 'image', 'icon')}),
        ('منوی بزرگ «دسته‌بندی فایل‌ها»', {
            'description': 'دسته‌ها با آیکن، توضیح کوتاه، تعداد فایل و پرفروش‌ترین محصولاتشان در منوی بزرگ هدر نمایش داده می‌شوند.',
            'fields': ('short_description', 'show_in_menu', 'menu_order'),
        }),
    )

    @admin.display(description='تاریخ ایجاد', ordering='created_at')
    def get_created_at_jalali(self, obj):
        return to_jalali(obj.created_at, '%a, %d %b %Y')


@admin.register(models.ProductBrand)
class ProductBrandAdmin(ModelAdminJalaliMixin, admin.ModelAdmin):
    list_display = ['title', 'brand_image', 'views', 'get_created_at_jalali']
    # برای autocomplete در فرم محصول
    search_fields = ['title']

    @admin.display(description='تاریخ ایجاد', ordering='created_at')
    def get_created_at_jalali(self, obj):
        return to_jalali(obj.created_at, '%a, %d %b %Y')


class _RoleRestrictedForm(forms.ModelForm):
    """فهرست فروشنده/نویسنده فقط نقش‌های مجاز را دارد، ولی مقدار فعلی رکوردهای قدیمی معتبر می‌ماند."""

    role_field = ''
    role_choices = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        field = self.fields.get(self.role_field)
        if field is None:
            return
        current = getattr(self.instance, f'{self.role_field}_id', None)
        allowed = get_user_model().objects.filter(type(self).role_choices())
        if current:
            allowed = get_user_model().objects.filter(pk__in=allowed.values('pk')) | \
                get_user_model().objects.filter(pk=current)
        field.queryset = allowed.distinct().order_by('username')


class ProductAdminForm(_RoleRestrictedForm):
    role_field = 'vendor'
    role_choices = staticmethod(vendor_choices)

    class Meta:
        model = models.Product
        fields = '__all__'


@admin.register(models.Product)
class ProductAdmin(RawHtmlAdminMixin, ModelAdminJalaliMixin, EnhancedAdminMixin, admin.ModelAdmin):
    form = ProductAdminForm
    list_display = ['pid', 'vendor', 'short_title', 'product_type', 'license_type', 'old_price', 'price', 'stock_count', 'sales_count', 'views', 'status', 'product_image', 'get_created_at_jalali']
    prepopulated_fields = {'slug': ('title',)}
    list_editable = ['old_price', 'price', 'stock_count', 'status']
    list_filter = ['status', 'product_type', 'license_type', 'is_unlimited', 'is_featured', 'category', 'brand']
    search_fields = ['title', 'short_description', 'pid', 'vendor__username', 'category__title', 'brand__title']
    autocomplete_fields = ['vendor', 'category', 'brand']
    date_hierarchy = 'created_at'
    list_select_related = ['vendor']
    readonly_fields = ['pid', 'views', 'sales_count', 'created_at', 'updated_at']
    inlines = [DigitalAssetInline, ProductImageAdmin]
    csv_filename = 'masaishop-products.csv'
    # ستون پیش‌نمایش تصویر در خروجی CSV معنا ندارد، پس ستون‌ها صریح تعیین شده‌اند
    csv_export_fields = ['pid', 'vendor', 'title', 'product_type', 'license_type', 'price',
                         'old_price', 'stock_count', 'sales_count', 'views', 'status',
                         'get_created_at_jalali']
    actions = ['mark_published', 'mark_draft', 'mark_featured', 'unmark_featured', 'export_selected_as_csv']
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
        ('کد HTML سفارشی (با پیش‌نمایش زنده)', {
            'classes': ('collapse',),
            'description': 'برای جدول مقایسه، ویدئوی آپارات، دکمه‌های سفارشی و… در تب «توضیحات تکمیلی». '
                           'فقط مدیر کل یا دارندهٔ مجوز «ویرایش کد HTML خام» می‌تواند آن را تغییر دهد.',
            'fields': ('custom_html_mode', 'custom_html'),
        }),
        ('آمار و شناسه (فقط خواندنی)', {
            'classes': ('collapse',),
            'fields': ('pid', 'views', 'sales_count', 'created_at', 'updated_at')
        }),
    )

    @admin.action(description='انتشار محصولات انتخاب‌شده')
    def mark_published(self, request, queryset):
        updated = queryset.update(status='published')
        self.message_user(request, f'{updated} محصول منتشر شد.')

    @admin.action(description='پیش‌نویس کردن محصولات انتخاب‌شده')
    def mark_draft(self, request, queryset):
        updated = queryset.update(status='draft')
        self.message_user(request, f'{updated} محصول به پیش‌نویس منتقل شد.')

    @admin.action(description='نشان‌گذاری به‌عنوان ویژه')
    def mark_featured(self, request, queryset):
        updated = queryset.update(is_featured=True)
        self.message_user(request, f'{updated} محصول ویژه شد.')

    @admin.action(description='برداشتن نشان ویژه')
    def unmark_featured(self, request, queryset):
        updated = queryset.update(is_featured=False)
        self.message_user(request, f'{updated} محصول از حالت ویژه خارج شد.')

    def short_title(self, obj):
        if len(obj.title) > 20:
            return obj.title[:20] + '...'
        return obj.title
    short_title.short_description = 'عنوان محصول'

    @admin.display(description='تاریخ ایجاد', ordering='created_at')
    def get_created_at_jalali(self, obj):
        return to_jalali(obj.created_at, '%a, %d %b %Y')


@admin.register(models.ProductComment)
class ProductCommentAdmin(ModelAdminJalaliMixin, admin.ModelAdmin):
    """دیدگاه‌ها پیش‌فرض «در انتظار تأیید» ثبت می‌شوند و از اینجا تأیید یا رد می‌شوند."""

    list_display = ['status_badge', 'short_product_title', 'author', 'short_body', 'status', 'get_created_at_jalali']
    list_display_links = ['short_body']
    list_editable = ['status']
    list_filter = ['status']
    search_fields = ['body', 'author__username', 'product__title']
    list_select_related = ['product', 'author']
    autocomplete_fields = ['product']
    raw_id_fields = ['author']
    actions = ['approve', 'reject']
    list_per_page = 50

    @admin.action(description='تأیید و انتشار دیدگاه‌های انتخاب‌شده')
    def approve(self, request, queryset):
        updated = queryset.exclude(status='published').update(status='published')
        self.message_user(request, f'{updated} دیدگاه تأیید و منتشر شد.')

    @admin.action(description='رد (پیش‌نویس) دیدگاه‌های انتخاب‌شده')
    def reject(self, request, queryset):
        updated = queryset.exclude(status='draft').update(status='draft')
        self.message_user(request, f'{updated} دیدگاه رد شد و نمایش داده نمی‌شود.')

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        pending = models.ProductComment.objects.filter(status='pending').count()
        if pending:
            extra_context['title'] = f'دیدگاه‌ها — {pending} مورد در انتظار تأیید'
        return super().changelist_view(request, extra_context=extra_context)

    @admin.display(description='')
    def status_badge(self, obj):
        colours = {'pending': '#d97706', 'published': '#059669', 'draft': '#6b7280'}
        return format_html('<span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:{}" title="{}"></span>',
                           colours.get(obj.status, '#6b7280'), obj.get_status_display())

    def short_product_title(self, obj):
        if len(obj.product.title) > 30:
            return obj.product.title[:30] + '...'
        return obj.product
    short_product_title.short_description = 'محصول مربوطه'

    def short_body(self, obj):
        if len(obj.body) > 60:
            return obj.body[:60] + '...'
        return obj.body
    short_body.short_description = 'متن دیدگاه'

    @admin.display(description='تاریخ ایجاد', ordering='created_at')
    def get_created_at_jalali(self, obj):
        return to_jalali(obj.created_at, '%a, %d %b %Y')


class ProductShowcaseItemInline(admin.TabularInline):
    model = models.ProductShowcaseItem
    extra = 1
    autocomplete_fields = ['product']
    fields = ['product', 'order']
    verbose_name = 'محصول'
    verbose_name_plural = 'محصولات این بخش (فقط در حالت «انتخاب دستی»)'


@admin.register(models.ProductShowcase)
class ProductShowcaseAdmin(admin.ModelAdmin):
    """ویترین‌های صفحهٔ اصلی؛ از جمله اسلایدر کوچک کنار «پیشنهادهای ویژه» (#bid-s)."""

    list_display = ['placement', 'title', 'source', 'item_count', 'limit', 'is_active', 'ends_at']
    list_editable = ['is_active']
    inlines = [ProductShowcaseItemInline]
    fieldsets = (
        (None, {
            'description': 'محل نمایش را انتخاب کنید و محصولات را دستی اضافه کنید یا یکی از حالت‌های خودکار را برگزینید.',
            'fields': ('placement', 'title', 'source', 'limit', 'autoplay_seconds', 'ends_at', 'is_active'),
        }),
    )

    @admin.display(description='تعداد محصول انتخاب‌شده')
    def item_count(self, obj):
        return obj.items.count()
