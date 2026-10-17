import logging
import os
from urllib.parse import unquote, urlsplit

from django.db import models
from core.thumbnails import admin_thumbnail
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator, URLValidator
from django_ckeditor_5.fields import CKEditor5Field

from accounts.roles import vendor_choices
from core.custom_html import CustomHtmlMixin
from shortuuid.django_fields import ShortUUIDField

from .storage import PrivateDigitalStorage

logger = logging.getLogger(__name__)


STATUS = (
    ("draft", "پیش‌نویس"),
    ("published", "منتشر شده")
)

PRODUCT_TYPES = (
    ("template", "قالب سایت"),
    ("plugin", "افزونه"),
    ("script", "اسکریپت و کد آماده"),
    ("software", "نرم‌افزار"),
    ("design_file", "فایل طراحی"),
    ("virtual", "محصول مجازی"),
)

LICENSE_TYPES = (
    ("single", "لایسنس تک‌کاربره"),
    ("multi", "لایسنس چندکاربردی"),
    ("lifetime", "لایسنس دائمی"),
    ("subscription", "اشتراک دوره‌ای"),
    ("gpl", "متن‌باز (GPL)"),
)


class ProductCategory(models.Model):
    title = models.CharField(max_length=100, unique=True, verbose_name='عنوان دسته بندی')
    slug = models.SlugField(max_length=100, unique=True, verbose_name='نامک')
    image = models.ImageField(upload_to='images/products/categories', null=True, blank=True, verbose_name='تصویر دسته بندی')
    icon = models.CharField(max_length=100, blank=True, help_text='نام آیکون Font Awesome مثلاً fa-wordpress', verbose_name='آیکون')
    # منوی بزرگ «دسته‌بندی فایل‌ها» (مگامنو)
    short_description = models.CharField(max_length=140, blank=True, verbose_name='توضیح کوتاه در منو',
                                         help_text='یک خط زیر نام دسته در منوی بزرگ؛ اختیاری.')
    show_in_menu = models.BooleanField(default=True, verbose_name='نمایش در منوی دسته‌بندی‌ها')
    menu_order = models.PositiveIntegerField(default=0, verbose_name='ترتیب در منو',
                                             help_text='عدد کوچک‌تر بالاتر نمایش داده می‌شود.')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ایجاد')

    def save(self, *args, **kwargs):
        """ریدایرکت خودکار ۳۰۱ هنگام تغییر نامک دسته‌بندی (حفظ اعتبار سئو)."""
        from core.models import Redirect
        if self.pk:
            try:
                old_slug = ProductCategory.objects.filter(pk=self.pk).values_list('slug', flat=True).first()
                if old_slug and old_slug != self.slug:
                    # جلوگیری از حلقه: ریدایرکت معکوس قبلی حذف شود
                    Redirect.objects.filter(old_path=f'/products/category/{self.slug}/').delete()
                    Redirect.objects.update_or_create(
                        old_path=f'/products/category/{old_slug}/',
                        defaults={
                            'new_path': f'/products/category/{self.slug}/',
                            'status_code': '301',
                            'is_active': True,
                            'note': 'تغییر نامک دسته‌بندی: ' + str(self.title),
                        },
                    )
            except Exception:
                # Saving the object must never fail because the SEO redirect
                # could not be recorded — but the failure must not be silent
                # either, or a broken redirect table stays invisible.
                logger.exception('ثبت ریدایرکت ۳۰۱ برای تغییر نامک انجام نشد.')
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = 'دسته بندی'
        verbose_name_plural = 'دسته بندی ها'
        ordering = ['menu_order', 'title']

    def category_image(self):
        return admin_thumbnail(self.image, self.title)
    category_image.short_description = 'تصویر'

    def __str__(self):
        return self.title


class ProductBrand(models.Model):
    title = models.CharField(max_length=100, unique=True, verbose_name='عنوان برند')
    slug = models.SlugField(max_length=100, unique=True, verbose_name='نامک')
    image = models.ImageField(upload_to='images/brands', null=True, blank=True, verbose_name='تصویر برند')
    views = models.IntegerField(default=0, verbose_name='بازدید ها')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ایجاد')

    def save(self, *args, **kwargs):
        """ریدایرکت خودکار ۳۰۱ هنگام تغییر نامک برند (حفظ اعتبار سئو)."""
        from core.models import Redirect
        if self.pk:
            try:
                old_slug = ProductBrand.objects.filter(pk=self.pk).values_list('slug', flat=True).first()
                if old_slug and old_slug != self.slug:
                    # جلوگیری از حلقه: ریدایرکت معکوس قبلی حذف شود
                    Redirect.objects.filter(old_path=f'/products/brand/{self.slug}/').delete()
                    Redirect.objects.update_or_create(
                        old_path=f'/products/brand/{old_slug}/',
                        defaults={
                            'new_path': f'/products/brand/{self.slug}/',
                            'status_code': '301',
                            'is_active': True,
                            'note': 'تغییر نامک برند: ' + str(self.title),
                        },
                    )
            except Exception:
                # Saving the object must never fail because the SEO redirect
                # could not be recorded — but the failure must not be silent
                # either, or a broken redirect table stays invisible.
                logger.exception('ثبت ریدایرکت ۳۰۱ برای تغییر نامک انجام نشد.')
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = 'برند / سازنده'
        verbose_name_plural = 'برندها / سازنده‌ها'

    def brand_image(self):
        return admin_thumbnail(self.image, self.title)
    brand_image.short_description = 'تصویر'

    def __str__(self):
        return self.title


class Product(CustomHtmlMixin, models.Model):
    pid = ShortUUIDField(unique=True, length=10, max_length=20, alphabet="abcdefgh12345", verbose_name="شناسه محصول")
    # فقط مدیران و کاربرانِ گروه «فروشندگان» قابل انتخاب‌اند (accounts.roles)؛
    # قبلاً فهرست همهٔ کاربران سایت در این فیلد نمایش داده می‌شد.
    vendor = models.ForeignKey(User, on_delete=models.CASCADE, limit_choices_to=vendor_choices,
                               verbose_name='فروشنده')
    category = models.ManyToManyField(ProductCategory, related_name='categories', verbose_name='دسته بندی مربوطه')
    title = models.CharField(max_length=300, unique=True, verbose_name='عنوان محصول')
    slug = models.SlugField(max_length=300, unique=True, allow_unicode=True, verbose_name='نامک')
    short_description = models.CharField(max_length=300, blank=True, verbose_name='توضیح کوتاه')
    description = CKEditor5Field(config_name='default', verbose_name='توضیحات تکمیلی')
    published_at = models.DateTimeField(null=True, blank=True, verbose_name='تاریخ انتشار')
    is_featured = models.BooleanField(default=False, verbose_name='ویژه')
    old_price = models.IntegerField(null=True, blank=True, verbose_name='قیمت قدیمی محصول')
    price = models.IntegerField(verbose_name='قیمت محصول')
    stock_count = models.IntegerField(default=0, verbose_name='تعداد موجود (برای لایسنس محدود)',
                                      help_text='برای محصولات با دانلود نامحدود نیازی به این عدد نیست')
    image = models.ImageField(upload_to='images/products', null=True, blank=True, verbose_name='تصویر محصول')
    status = models.CharField(choices=STATUS, max_length=10, default='published', verbose_name='وضعیت')
    views = models.IntegerField(default=0, verbose_name='بازدید ها')
    sales_count = models.IntegerField(default=0, verbose_name='تعداد فروش')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ایجاد')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاریخ به‌روزرسانی')
    meta_title = models.CharField(max_length=70, blank=True, verbose_name='عنوان سئو')
    meta_description = models.CharField(max_length=160, blank=True, verbose_name='توضیحات سئو')
    canonical_url = models.URLField(blank=True, verbose_name='آدرس canonical')

    # مشخصات محصولات دیجیتال
    product_type = models.CharField(choices=PRODUCT_TYPES, max_length=20, default='template',
                                    verbose_name='نوع محصول', help_text='قالب، افزونه، اسکریپت، نرم‌افزار، فایل طراحی یا محصول مجازی')
    brand = models.ManyToManyField(ProductBrand, related_name='product_brands', blank=True, verbose_name='برند / سازنده')
    license_type = models.CharField(choices=LICENSE_TYPES, max_length=20, default='single', verbose_name='نوع لایسنس')
    is_unlimited = models.BooleanField(default=True, verbose_name='دانلود نامحدود',
                                       help_text='اگر فعال باشد محدودیتی برای تعداد فروش و دانلود وجود ندارد')
    demo_url = models.URLField(blank=True, verbose_name='لینک پیش‌نمایش (دمو)')
    documentation_url = models.URLField(blank=True, verbose_name='لینک مستندات')
    requirements = models.TextField(blank=True, verbose_name='پیش‌نیازها',
                                    help_text='هر خط یک پیش‌نیاز است، مثلاً: PHP 8.1+')
    operating_system = models.CharField(max_length=100, blank=True, null=True, verbose_name='سیستم عامل سازگار')
    support_duration = models.CharField(max_length=60, blank=True, verbose_name='مدت پشتیبانی')
    update_duration = models.CharField(max_length=60, blank=True, verbose_name='مدت دریافت به‌روزرسانی')

    def save(self, *args, **kwargs):
        """ریدایرکت خودکار ۳۰۱ هنگام تغییر نامک محصول (حفظ اعتبار سئو)."""
        from core.models import Redirect
        if self.pk:
            try:
                old_slug = Product.objects.filter(pk=self.pk).values_list('slug', flat=True).first()
                if old_slug and old_slug != self.slug:
                    # جلوگیری از حلقه: ریدایرکت معکوس قبلی حذف شود
                    Redirect.objects.filter(old_path=f'/products/{self.pid}/{self.slug}/').delete()
                    Redirect.objects.update_or_create(
                        old_path=f'/products/{self.pid}/{old_slug}/',
                        defaults={
                            'new_path': f'/products/{self.pid}/{self.slug}/',
                            'status_code': '301',
                            'is_active': True,
                            'note': 'تغییر نامک محصول: ' + str(self.title),
                        },
                    )
            except Exception:
                # Saving the object must never fail because the SEO redirect
                # could not be recorded — but the failure must not be silent
                # either, or a broken redirect table stays invisible.
                logger.exception('ثبت ریدایرکت ۳۰۱ برای تغییر نامک انجام نشد.')
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = 'محصول'
        verbose_name_plural = 'محصولات'
        ordering = ['-created_at', '-id']
        constraints = [
            models.CheckConstraint(condition=models.Q(price__gte=0), name='product_price_nonnegative'),
            models.CheckConstraint(
                condition=models.Q(old_price__isnull=True) | models.Q(old_price__gte=0),
                name='product_old_price_nonnegative',
            ),
            models.CheckConstraint(condition=models.Q(stock_count__gte=0), name='product_stock_nonnegative'),
            models.CheckConstraint(condition=models.Q(sales_count__gte=0), name='product_sales_count_nonnegative'),
        ]

    @property
    def is_available(self):
        """محصولات دیجیتال با دانلود نامحدود همیشه موجود هستند."""
        return self.is_unlimited or self.stock_count > 0

    @property
    def digital_info(self):
        """دسترسی امن به فایل دیجیتال محصول (در صورت وجود)."""
        return getattr(self, 'digital_asset', None)

    def discount_percentage(self):
        if self.old_price and self.price < self.old_price:
            discount = ((self.old_price - self.price) / self.old_price) * 100
            return int(discount) if discount > 0 else None
        return 0

    def product_image(self):
        return admin_thumbnail(self.image, self.title)
    product_image.short_description = 'تصویر'

    def __str__(self):
        return self.title


def _extension_of(name):
    """'ZIP' for 'theme-v2.zip'; '' when the name has no sensible extension."""
    base = os.path.basename(name or '')
    if '.' not in base:
        return ''
    extension = base.rsplit('.', 1)[-1]
    return extension.upper() if extension.isalnum() and len(extension) <= 6 else ''


class DigitalAsset(models.Model):
    """The file a buyer downloads: uploaded to private storage or a download link.

    Either way the buyer only reaches it through ``/downloads/<token>/``, which
    checks the order, the expiry and the download limit first; a link is never
    printed in a page.  Links suit large files kept on a download server or host.
    """

    SOURCE_UPLOAD = 'upload'
    SOURCE_LINK = 'link'
    SOURCES = (
        (SOURCE_UPLOAD, 'آپلود فایل روی سایت'),
        (SOURCE_LINK, 'لینک دانلود (فایل روی سرور دانلود یا هاست دیگر)'),
    )

    product = models.OneToOneField(Product, related_name='digital_asset', on_delete=models.CASCADE, verbose_name='محصول')
    source = models.CharField(
        max_length=10, choices=SOURCES, default=SOURCE_UPLOAD, verbose_name='نحوهٔ تحویل فایل',
        help_text='فایل را روی سایت آپلود کنید یا لینک دانلود آن را بگذارید. در هر دو حالت خریدار '
                  'فقط بعد از پرداخت و از مسیر امن «دانلودهای من» به فایل می‌رسد.',
    )
    file = models.FileField(
        upload_to='digital-products/',
        storage=PrivateDigitalStorage(),
        blank=True,
        verbose_name='فایل محصول',
        help_text='برای حالت «آپلود فایل». فایل در پوشهٔ خصوصی ذخیره می‌شود و آدرس عمومی ندارد.',
    )
    external_url = models.URLField(
        max_length=1000, blank=True, validators=[URLValidator(schemes=['http', 'https'])],
        verbose_name='لینک دانلود',
        help_text='برای حالت «لینک دانلود»: لینک مستقیم فایل (مثلاً https://dl.example.com/theme.zip). '
                  'این لینک در صفحه‌ها نمایش داده نمی‌شود و خریدار هنگام دانلود به آن هدایت می‌شود.',
    )
    preview_file = models.FileField(upload_to='digital-previews/', null=True, blank=True, verbose_name='فایل پیش‌نمایش')
    file_size = models.PositiveBigIntegerField(default=0, editable=False, verbose_name='حجم فایل')
    file_type = models.CharField(max_length=80, blank=True, verbose_name='فرمت فایل',
                                 help_text='اگر خالی بماند از پسوند فایل یا لینک خوانده می‌شود (مثلاً ZIP).')
    version = models.CharField(max_length=30, blank=True, verbose_name='نسخه')
    changelog = models.TextField(blank=True, verbose_name='تغییرات نسخه', help_text='هر خط یک مورد از تغییرات نسخه')
    download_count = models.PositiveIntegerField(default=0, editable=False, verbose_name='تعداد دانلود')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'فایل دیجیتال'
        verbose_name_plural = 'فایل‌های دیجیتال'

    @property
    def is_link(self):
        return self.source == self.SOURCE_LINK

    def clean(self):
        super().clean()
        if self.is_link:
            if not self.external_url:
                raise ValidationError({'external_url': 'برای «لینک دانلود»، آدرس لینک فایل را وارد کنید.'})
        elif not self.file:
            raise ValidationError({'file': 'برای «آپلود فایل»، فایل محصول را انتخاب کنید '
                                           '(یا نحوهٔ تحویل را «لینک دانلود» بگذارید).'})

    def save(self, *args, **kwargs):
        if self.is_link:
            # The size of a linked file is whatever the admin entered (or unknown).
            if not self.file_type:
                self.file_type = _extension_of(unquote(urlsplit(self.external_url).path))
        elif self.file:
            try:
                self.file_size = self.file.size
            except (OSError, ValueError):
                # The file may not be readable yet (or may have been removed
                # from storage); the size is metadata, not a hard requirement.
                logger.warning('حجم فایل دیجیتال خوانده نشد: %s', self.file.name, exc_info=True)
            if not self.file_type:
                self.file_type = _extension_of(self.file.name)
        super().save(*args, **kwargs)

    def is_deliverable(self):
        """True when a buyer can actually receive something right now."""
        if self.is_link:
            return bool(self.external_url)
        if not self.file:
            return False
        try:
            # PrivateDigitalStorage also finds files still in the legacy media folder.
            return self.file.storage.exists(self.file.name)
        except (OSError, ValueError):
            return False

    @property
    def file_size_display(self):
        size = self.file_size
        if not size:
            return '-'
        if size >= 1024 ** 3:
            return f'{size / 1024 ** 3:.2f} گیگابایت'
        if size >= 1024 ** 2:
            return f'{size / 1024 ** 2:.1f} مگابایت'
        return f'{size / 1024:.0f} کیلوبایت'

    def __str__(self):
        return self.product.title


def missing_file_q():
    """Products a buyer would get nothing for: no file row, or an empty upload/link."""
    return (
        models.Q(digital_asset__isnull=True)
        | models.Q(digital_asset__source=DigitalAsset.SOURCE_UPLOAD, digital_asset__file='')
        | models.Q(digital_asset__source=DigitalAsset.SOURCE_LINK, digital_asset__external_url='')
    )


class ProductImage(models.Model):
    product = models.ForeignKey(Product, related_name="product_images", on_delete=models.CASCADE, verbose_name="محصول")
    images = models.ImageField(upload_to='images/products/product_images', verbose_name="تصاویر محصولات")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ایجاد')

    class Meta:
        verbose_name = "تصویر محصول"
        verbose_name_plural = "تصاویر محصولات"

    def __str__(self):
        return self.product.title


class ProductComment(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='product_comments', verbose_name='محصول مربوطه')
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='product_comments', verbose_name='نویسنده دیدگاه')
    body = models.TextField(verbose_name='متن دیدگاه')
    # دیدگاه پیش از نمایش عمومی باید تأیید شود؛ رابط کاربری هم از ابتدا به
    # کاربر همین را وعده می‌دهد («پس از بررسی نمایش داده می‌شود») ولی پیش‌فرضِ
    # قبلی انتشار فوری بود. تأیید از ادمین (list_editable وضعیت) انجام می‌شود.
    status = models.CharField(
        choices=STATUS + (('pending', 'در انتظار تأیید'),),
        max_length=10, default='pending', verbose_name='وضعیت',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ایجاد')

    class Meta:
        verbose_name = 'نظر'
        verbose_name_plural = 'نظرات'

    def __str__(self):
        return self.product.title


class ProductShowcase(models.Model):
    """ویترین‌های محصولِ صفحهٔ اصلی؛ مدیر محصولات هر بخش را انتخاب می‌کند.

    قبلاً اسلایدر کوچک کنار «پیشنهادهای ویژه» (#bid-s) فقط چهار محصولِ
    جدیدِ *بدون قیمت قبلی* را نشان می‌داد؛ وقتی همهٔ محصولات تخفیف داشتند،
    آن بخش خالی می‌ماند و راهی برای انتخاب محصول در آن نبود.
    """

    PLACEMENTS = (
        ('home_offers', 'صفحهٔ اصلی — اسلایدر بزرگ «پیشنهادهای ویژه»'),
        ('home_side', 'صفحهٔ اصلی — اسلایدر کوچک کنار پیشنهادها'),
        ('home_discounts', 'صفحهٔ اصلی — ردیف تخفیف‌های ویژه'),
        ('home_bestsellers', 'صفحهٔ اصلی — ردیف پرفروش‌ترین‌ها'),
    )
    SOURCES = (
        ('manual', 'انتخاب دستی (محصولات جدول زیر)'),
        ('latest', 'خودکار: جدیدترین محصولات'),
        ('popular', 'خودکار: پربازدیدترین محصولات'),
        ('best_selling', 'خودکار: پرفروش‌ترین محصولات'),
        ('discounted', 'خودکار: بیشترین درصد تخفیف'),
        ('featured', 'خودکار: محصولات «ویژه»'),
    )

    placement = models.CharField(max_length=30, choices=PLACEMENTS, unique=True, verbose_name='محل نمایش')
    title = models.CharField(max_length=100, blank=True, verbose_name='عنوان بخش',
                             help_text='مثلاً «پیشنهاد لحظه‌ای»؛ خالی = بدون عنوان.')
    source = models.CharField(max_length=20, choices=SOURCES, default='manual', verbose_name='منبع محصولات',
                              help_text='در حالت دستی اگر هیچ محصول منتشرشده‌ای انتخاب نشده باشد، جدیدترین‌ها نمایش داده می‌شوند.')
    products = models.ManyToManyField(Product, through='ProductShowcaseItem', blank=True,
                                      related_name='showcases', verbose_name='محصولات')
    limit = models.PositiveSmallIntegerField(default=8, validators=[MinValueValidator(1), MaxValueValidator(24)],
                                             verbose_name='حداکثر تعداد محصول')
    autoplay_seconds = models.PositiveSmallIntegerField(
        default=5, validators=[MinValueValidator(2), MaxValueValidator(30)],
        verbose_name='زمان هر اسلاید (ثانیه)', help_text='برای اسلایدرها.')
    ends_at = models.DateTimeField(null=True, blank=True, verbose_name='پایان نمایش (اختیاری)',
                                   help_text='پس از این زمان بخش پنهان می‌شود و تا آن زمان شمارش معکوس نمایش داده می‌شود.')
    is_active = models.BooleanField(default=True, verbose_name='فعال')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='آخرین تغییر')

    class Meta:
        verbose_name = 'ویترین صفحهٔ اصلی'
        verbose_name_plural = 'ویترین‌های صفحهٔ اصلی'
        ordering = ['placement']

    def __str__(self):
        return self.title or self.get_placement_display()


class ProductShowcaseItem(models.Model):
    showcase = models.ForeignKey(ProductShowcase, on_delete=models.CASCADE, related_name='items',
                                 verbose_name='ویترین')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='showcase_items',
                                verbose_name='محصول')
    order = models.PositiveIntegerField(default=0, verbose_name='ترتیب')

    class Meta:
        verbose_name = 'محصول ویترین'
        verbose_name_plural = 'محصولات ویترین'
        ordering = ['order', 'id']
        constraints = [
            models.UniqueConstraint(fields=['showcase', 'product'], name='showcase_product_once'),
        ]

    def __str__(self):
        return f'{self.showcase} — {self.product}'
