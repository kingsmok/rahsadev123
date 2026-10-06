from django.db import models
from ckeditor_uploader.fields import RichTextUploadingField
from django.utils.html import format_html


BANNER_TYPES = (
    ('main_slider', 'اسلایدر اصلی'),
    ('small_banner', 'بنر های کوچک (4 تایی)'),
    ('large_banner', 'بنر های بزرگ (2 تایی)'),
    ('single_banner', 'بنر تک'),
)

STATUS = (
    ("draft", "پیش نویس شود"),
    ("published", "منتشر شود"),
)


class SiteSettings(models.Model):
    site_name = models.CharField(max_length=100, default='فایل‌مارکت', verbose_name='نام سایت')
    site_slogan = models.CharField(max_length=200, blank=True, default='مارکت فایل، نرم‌افزار و محصولات مجازی', verbose_name='شعار سایت')
    logo = models.ImageField(upload_to='settings/', null=True, blank=True, verbose_name='لوگو (اختیاری)',
                             help_text='اگر خالی باشد لوگوی متنی نمایش داده می‌شود')
    text_about_us = RichTextUploadingField(null=True, blank=True, verbose_name='متن درباره ما')
    text_contact_us = models.TextField(null=True, blank=True, verbose_name='متن تماس با ما')
    footer_description = models.TextField(blank=True, verbose_name='متن معرفی فوتر',
                                          help_text='اگر خالی باشد متن پیش‌فرض نمایش داده می‌شود')
    address = models.CharField(max_length=250, null=True, blank=True, verbose_name='آدرس')
    phone1 = models.CharField(max_length=14, null=True, blank=True, verbose_name='شماره تلفن اول')
    phone2 = models.CharField(max_length=14, null=True, blank=True, verbose_name='شماره تلفن دوم')
    email1 = models.CharField(max_length=250, null=True, blank=True, verbose_name='ایمیل اول')
    email2 = models.CharField(max_length=250, null=True, blank=True, verbose_name='ایمیل دوم')
    copy_right = models.CharField(max_length=255, verbose_name='متن کپی رایت')
    instagram_link = models.CharField(max_length=250, null=True, blank=True, default='https://instagram.com/username', verbose_name='لینک اینستاگرام')
    telegram_link = models.CharField(max_length=250, null=True, blank=True, default='https://t.me/username', verbose_name='لینک تلگرام')
    whatsapp_link = models.CharField(max_length=250, null=True, blank=True, verbose_name='لینک واتساپ')
    twitter_link = models.CharField(max_length=250, null=True, blank=True, verbose_name='لینک توییتر (X)')
    youtube_link = models.CharField(max_length=250, null=True, blank=True, verbose_name='لینک یوتیوب')
    linkedin_link = models.CharField(max_length=250, null=True, blank=True, verbose_name='لینک لینکدین')
    enamad_link = models.URLField(blank=True, null=True, verbose_name='لینک نشان اینماد',
                                  help_text='اگر خالی باشد نشان در فوتر نمایش داده نمی‌شود')
    samandehi_link = models.URLField(blank=True, null=True, verbose_name='لینک نشان ساماندهی',
                                     help_text='اگر خالی باشد نشان در فوتر نمایش داده نمی‌شود')
    default_meta_title = models.CharField(max_length=70, blank=True, verbose_name='عنوان سئوی پیش‌فرض')
    default_meta_description = models.CharField(max_length=160, blank=True, verbose_name='توضیحات سئوی پیش‌فرض')
    google_site_verification = models.CharField(max_length=120, blank=True, verbose_name='کد تأیید Google Search Console')
    bing_site_verification = models.CharField(max_length=120, blank=True, verbose_name='کد تأیید Bing Webmaster')
    products_per_page = models.PositiveIntegerField(default=9, verbose_name='تعداد محصول در هر صفحه')

    class Meta:
        verbose_name = 'تنظیمات سایت'
        verbose_name_plural = 'تنظیمات سایت'


class Banner(models.Model):
    title = models.CharField(max_length=200, verbose_name='عنوان بنر')
    image = models.ImageField(upload_to='banners/', verbose_name='تصویر بنر')
    url = models.URLField(verbose_name='لینک مقصد')
    banner_type = models.CharField(choices=BANNER_TYPES, max_length=20, verbose_name='نوع بنر')
    status = models.CharField(choices=STATUS, max_length=10, default='published', verbose_name='وضعیت')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ایجاد')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاریخ به‌روزرسانی')

    class Meta:
        verbose_name = 'بنر'
        verbose_name_plural = 'بنر ها'

    def banner_image(self):
        if self.image:
            return format_html(f'<img src="{self.image.url}" width="100px" height="50px">')
        return format_html(f'<h3 style="color: red">تصویر ندارد</h3>')

    def __str__(self):
        return self.title


class ContactUs(models.Model):
    first_name = models.CharField(max_length=100, verbose_name='نام')
    last_name = models.CharField(max_length=100, verbose_name='نام خانوادگی')
    phone = models.CharField(max_length=14, verbose_name='شماره تماس')
    message = models.TextField(verbose_name='متن پیام')
    date_send = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ارسال')

    class Meta:
        ordering = ["-date_send"]
        verbose_name = "تماس با ما"
        verbose_name_plural = "تماس با ما"

    def __str__(self):
        return f'{self.first_name} {self.last_name}'


class Redirect(models.Model):
    """ریدایرکت قابل مدیریت از پنل — هدایت آدرس‌های قدیمی به جدید.

    نوع ۳۰۱ (دائمی) برای سئو استفاده می‌شود تا اعتبار آدرس قدیمی به جدید منتقل شود.
    """

    STATUS_CODES = (
        ('301', 'دائمی (301)'),
        ('302', 'موقت (302)'),
    )

    old_path = models.CharField(max_length=500, unique=True, verbose_name='آدرس قدیمی')
    new_path = models.CharField(max_length=500, verbose_name='آدرس جدید')
    status_code = models.CharField(max_length=3, choices=STATUS_CODES, default='301', verbose_name='نوع ریدایرکت')
    is_active = models.BooleanField(default=True, verbose_name='فعال')
    hits = models.PositiveIntegerField(default=0, editable=False, verbose_name='دفعات استفاده')
    note = models.CharField(max_length=255, blank=True, verbose_name='توضیح')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ایجاد')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاریخ به‌روزرسانی')

    class Meta:
        verbose_name = 'ریدایرکت'
        verbose_name_plural = 'ریدایرکت‌ها'
        ordering = ['old_path']

    def __str__(self):
        return f'{self.old_path} → {self.new_path}'

    @staticmethod
    def normalize_path(path):
        """نرمال‌سازی مسیر: بدون فاصله اضافه، با اسلش ابتدا."""
        path = (path or '').strip()
        if not path:
            return '/'
        if not path.startswith('/') and not path.startswith(('http://', 'https://')):
            path = '/' + path
        return path

    def save(self, *args, **kwargs):
        self.old_path = self.normalize_path(self.old_path)
        if not self.new_path.startswith(('http://', 'https://')):
            self.new_path = self.normalize_path(self.new_path)
        super().save(*args, **kwargs)
