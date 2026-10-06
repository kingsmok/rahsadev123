from django.db import models
from django.contrib.auth.models import User
from ckeditor_uploader.fields import RichTextUploadingField
from django.utils.html import format_html
from shortuuid.django_fields import ShortUUIDField


STATUS = (
    ("draft", "پیش نویس شود"),
    ("published", "منتشر شود")
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
                pass
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = 'دسته بندی'
        verbose_name_plural = 'دسته بندی ها'
        ordering = ['title']

    def category_image(self):
        if self.image:
            return format_html(f'<img src="{self.image.url}" width="50px" height="50px">')
        return format_html(f'<h3 style="color: red">تصویر ندارد</h3>')

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
                pass
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = 'برند / سازنده'
        verbose_name_plural = 'برندها / سازنده‌ها'

    def brand_image(self):
        if self.image:
            return format_html(f'<img src="{self.image.url}" width="50px" height="50px">')
        return format_html(f'<h3 style="color: red">تصویر ندارد</h3>')

    def __str__(self):
        return self.title


class Product(models.Model):
    pid = ShortUUIDField(unique=True, length=10, max_length=20, alphabet="abcdefgh12345", verbose_name="شناسه محصول")
    vendor = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='فروشنده')
    category = models.ManyToManyField(ProductCategory, related_name='categories', verbose_name='دسته بندی مربوطه')
    title = models.CharField(max_length=300, unique=True, verbose_name='عنوان محصول')
    slug = models.SlugField(max_length=300, unique=True, allow_unicode=True, verbose_name='نامک')
    short_description = models.CharField(max_length=300, blank=True, verbose_name='توضیح کوتاه')
    description = RichTextUploadingField(verbose_name='توضیحات تکمیلی')
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
                pass
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
        if self.image:
            return format_html(f'<img src="{self.image.url}" width="50px" height="50px">')
        return format_html(f'<h3 style="color: red">تصویر ندارد</h3>')

    def __str__(self):
        return self.title


class DigitalAsset(models.Model):
    product = models.OneToOneField(Product, related_name='digital_asset', on_delete=models.CASCADE, verbose_name='محصول')
    file = models.FileField(upload_to='digital-products/', verbose_name='فایل محصول')
    preview_file = models.FileField(upload_to='digital-previews/', null=True, blank=True, verbose_name='فایل پیش‌نمایش')
    file_size = models.PositiveBigIntegerField(default=0, editable=False, verbose_name='حجم فایل')
    file_type = models.CharField(max_length=80, blank=True, verbose_name='فرمت فایل')
    version = models.CharField(max_length=30, blank=True, verbose_name='نسخه')
    changelog = models.TextField(blank=True, verbose_name='تغییرات نسخه', help_text='هر خط یک مورد از تغییرات نسخه')
    download_count = models.PositiveIntegerField(default=0, editable=False, verbose_name='تعداد دانلود')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'فایل دیجیتال'
        verbose_name_plural = 'فایل‌های دیجیتال'

    def save(self, *args, **kwargs):
        if self.file:
            try:
                self.file_size = self.file.size
            except Exception:
                pass
            if not self.file_type:
                self.file_type = self.file.name.rsplit('.', 1)[-1].upper() if '.' in self.file.name else ''
        super().save(*args, **kwargs)

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
    status = models.CharField(choices=STATUS, max_length=10, default='published', verbose_name='وضعیت')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ایجاد')

    class Meta:
        verbose_name = 'نظر'
        verbose_name_plural = 'نظرات'

    def __str__(self):
        return self.product.title
