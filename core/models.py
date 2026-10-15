from django.db import models
from core.thumbnails import admin_thumbnail
from core.validators import validate_site_link
from django_ckeditor_5.fields import CKEditor5Field


BANNER_TYPES = (
    ('main_slider', 'اسلایدر اصلی'),
    ('small_banner', 'بنر های کوچک (4 تایی)'),
    ('large_banner', 'بنر های بزرگ (2 تایی)'),
    ('single_banner', 'بنر تک'),
)

STATUS = (
    ("draft", "پیش‌نویس"),
    ("published", "منتشر شده"),
)

# ارتفاع نمایش بنر. «خودکار» یعنی همان نسبت ابعاد تصویر (رفتار قبلی)؛ بقیه
# ارتفاع ثابتی می‌دهند و تصویر با object-fit: cover بریده می‌شود.
BANNER_SIZES = (
    ('auto', 'خودکار (مطابق نسبت تصویر)'),
    ('sm', 'کوتاه'),
    ('md', 'متوسط'),
    ('lg', 'بلند'),
    ('xl', 'خیلی بلند'),
)

BANNER_WIDTHS = (
    ('default', 'پیش‌فرضِ نوع بنر'),
    ('full', 'تمام عرض'),
    ('half', 'نصف عرض (دو بنر در یک ردیف)'),
    ('third', 'یک‌سوم عرض (سه بنر در یک ردیف)'),
    ('quarter', 'یک‌چهارم عرض (چهار بنر در یک ردیف)'),
)

BANNER_TEXT_POSITIONS = (
    ('start', 'راست'),
    ('center', 'وسط'),
    ('end', 'چپ'),
)

BANNER_TEXT_THEMES = (
    ('light', 'متن روشن روی سایهٔ تیره'),
    ('dark', 'متن تیره روی سایهٔ روشن'),
)

# متن پیش‌فرض اسلایدر اصلی؛ قبلاً در قالب ثابت بود و حالا فقط وقتی «متن بنر»
# خالی است نمایش داده می‌شود تا ظاهر بنرهای قبلی تغییر نکند.
DEFAULT_SLIDER_DESCRIPTION = 'دانلود آنی محصولات دیجیتال با لایسنس رسمی و پشتیبانی تخصصی'

_BANNER_COLUMNS = {
    'full': 'col-12',
    'half': 'col-12 col-md-6',
    'third': 'col-12 col-md-4',
    'quarter': 'col-6 col-lg-3',
}
_BANNER_DEFAULT_COLUMNS = {
    'small_banner': 'col-6 col-lg-3',
    'large_banner': 'col-12 col-lg-6',
    'single_banner': 'col-12',
    'main_slider': 'col-12',
}


class SiteSettings(models.Model):
    """هویت و تنظیمات سراسری فروشگاه.

    فقط یک ردیف معتبر است (اولین ردیف بر اساس pk)؛ همهٔ بخش‌ها — فروشگاه، پنل
    کاربری، Django Admin، پنل مدیریت، manifest، صفحهٔ آفلاین و آیکن تب مرورگر —
    نام و لوگو را از طریق ``core.branding`` از همین ردیف می‌خوانند.
    """

    # فاوآیکن باید بدون افت کیفیت ذخیره شود؛ تبدیل خودکار WebP (core.signals)
    # برای این فیلد انجام نمی‌شود.
    image_optimisation_exclude = ('favicon',)

    site_name = models.CharField(max_length=100, default='فایل‌مارکت', verbose_name='نام سایت')
    site_slogan = models.CharField(max_length=200, blank=True, default='مارکت فایل، نرم‌افزار و محصولات مجازی', verbose_name='شعار سایت')
    logo = models.ImageField(upload_to='settings/', null=True, blank=True, verbose_name='لوگو (اختیاری)',
                             help_text='در هدر فروشگاه، Django Admin و پنل مدیریت نمایش داده می‌شود. '
                                       'اگر خالی باشد لوگوی متنی (حرف اول نام سایت) نمایش داده می‌شود.')
    favicon = models.ImageField(upload_to='settings/', null=True, blank=True,
                                verbose_name='آیکن تب مرورگر (فاوآیکن)',
                                help_text='آیکن کوچک بالای تب مرورگر، آیکن نصب اپ (PWA) و آیکن صفحهٔ اصلی آیفون. '
                                          'بهترین نتیجه: تصویر مربعی PNG با حداقل ۵۱۲×۵۱۲ پیکسل و پس‌زمینهٔ شفاف '
                                          '(ICO و JPG هم پذیرفته می‌شود). اگر خالی باشد از لوگو ساخته می‌شود.')
    text_about_us = CKEditor5Field(config_name='default', null=True, blank=True, verbose_name='متن درباره ما')
    text_contact_us = models.TextField(null=True, blank=True, verbose_name='متن تماس با ما')
    footer_description = models.TextField(blank=True, verbose_name='متن معرفی فوتر',
                                          help_text='اگر خالی باشد متن پیش‌فرض نمایش داده می‌شود')
    address = models.CharField(max_length=250, null=True, blank=True, verbose_name='آدرس')
    phone1 = models.CharField(max_length=14, null=True, blank=True, verbose_name='شماره تلفن اول')
    phone2 = models.CharField(max_length=14, null=True, blank=True, verbose_name='شماره تلفن دوم')
    email1 = models.CharField(max_length=250, null=True, blank=True, verbose_name='ایمیل اول')
    email2 = models.CharField(max_length=250, null=True, blank=True, verbose_name='ایمیل دوم')
    copy_right = models.CharField(max_length=255, verbose_name='متن کپی رایت')
    # شبکه‌های اجتماعی. مقدار نمونهٔ قدیمی (…/username) در سایت نمایش داده
    # نمی‌شود (core.social)؛ فیلد خالی هم یعنی آن شبکه نمایش داده نشود.
    instagram_link = models.CharField(max_length=250, null=True, blank=True, default='', verbose_name='لینک اینستاگرام')
    telegram_link = models.CharField(max_length=250, null=True, blank=True, default='', verbose_name='لینک تلگرام')
    whatsapp_link = models.CharField(max_length=250, null=True, blank=True, verbose_name='لینک واتساپ',
                                     help_text='مثلاً https://wa.me/989121234567')
    twitter_link = models.CharField(max_length=250, null=True, blank=True, verbose_name='لینک توییتر (X)')
    youtube_link = models.CharField(max_length=250, null=True, blank=True, verbose_name='لینک یوتیوب')
    linkedin_link = models.CharField(max_length=250, null=True, blank=True, verbose_name='لینک لینکدین')
    facebook_link = models.CharField(max_length=250, blank=True, default='', verbose_name='لینک فیسبوک')
    pinterest_link = models.CharField(max_length=250, blank=True, default='', verbose_name='لینک پینترست')
    github_link = models.CharField(max_length=250, blank=True, default='', verbose_name='لینک گیت‌هاب')
    aparat_link = models.CharField(max_length=250, blank=True, default='', verbose_name='لینک آپارات')
    eitaa_link = models.CharField(max_length=250, blank=True, default='', verbose_name='لینک ایتا',
                                  help_text='مثلاً https://eitaa.com/your_channel')
    rubika_link = models.CharField(max_length=250, blank=True, default='', verbose_name='لینک روبیکا',
                                   help_text='مثلاً https://rubika.ir/your_channel')
    bale_link = models.CharField(max_length=250, blank=True, default='', verbose_name='لینک بله',
                                 help_text='مثلاً https://ble.ir/your_channel')
    soroush_link = models.CharField(max_length=250, blank=True, default='', verbose_name='لینک سروش پلاس',
                                    help_text='مثلاً https://splus.ir/your_channel')
    igap_link = models.CharField(max_length=250, blank=True, default='', verbose_name='لینک آی‌گپ')
    virgool_link = models.CharField(max_length=250, blank=True, default='', verbose_name='لینک ویرگول')
    enamad_link = models.URLField(blank=True, null=True, verbose_name='لینک نشان اینماد',
                                  help_text='اگر خالی باشد نشان در فوتر نمایش داده نمی‌شود')
    samandehi_link = models.URLField(blank=True, null=True, verbose_name='لینک نشان ساماندهی',
                                     help_text='اگر خالی باشد نشان در فوتر نمایش داده نمی‌شود')
    default_meta_title = models.CharField(max_length=70, blank=True, verbose_name='عنوان سئوی پیش‌فرض')
    default_meta_description = models.CharField(max_length=160, blank=True, verbose_name='توضیحات سئوی پیش‌فرض')
    google_site_verification = models.CharField(max_length=120, blank=True, verbose_name='کد تأیید Google Search Console')
    bing_site_verification = models.CharField(max_length=120, blank=True, verbose_name='کد تأیید Bing Webmaster')
    products_per_page = models.PositiveIntegerField(default=9, verbose_name='تعداد محصول در هر صفحه')
    # نسخهٔ برند: آدرس لوگو و آیکن‌ها با این زمان نسخه‌دار می‌شوند تا مرورگرها
    # پس از هر ذخیره، تصویر جدید را بگیرند و نسخهٔ کش‌شدهٔ قبلی را نشان ندهند.
    updated_at = models.DateTimeField(auto_now=True, verbose_name='آخرین به‌روزرسانی')

    class Meta:
        verbose_name = 'تنظیمات سایت'
        verbose_name_plural = 'تنظیمات سایت'

    def __str__(self):
        return self.site_name or 'تنظیمات سایت'


class Banner(models.Model):
    title = models.CharField(max_length=200, verbose_name='عنوان بنر')
    image = models.ImageField(upload_to='banners/', verbose_name='تصویر بنر')
    mobile_image = models.ImageField(
        upload_to='banners/', null=True, blank=True, verbose_name='تصویر نسخهٔ موبایل (اختیاری)',
        help_text='روی صفحه‌های کوچک‌تر از ۷۶۸ پیکسل به جای تصویر اصلی نمایش داده می‌شود؛ '
                  'برای اسلایدر، تصویر عمودی یا مربعی بهتر دیده می‌شود.')
    # قبلاً URLField اجباری بود: مسیرهای داخلی سایت (مثل /product/) پذیرفته
    # نمی‌شد و بنر بدون لینک هم ممکن نبود.
    url = models.CharField(
        max_length=500, blank=True, validators=[validate_site_link], verbose_name='لینک مقصد',
        help_text='آدرس کامل (https://…) یا مسیر داخلی سایت مثل /product/ ؛ خالی = بنر بدون لینک.')
    open_in_new_tab = models.BooleanField(default=False, verbose_name='باز شدن لینک در تب جدید')
    banner_type = models.CharField(choices=BANNER_TYPES, max_length=20, verbose_name='نوع بنر')

    # متن روی بنر
    show_text = models.BooleanField(
        default=True, verbose_name='نمایش متن روی بنر',
        help_text='برای اسلایدر، عنوان و متن روی تصویر نمایش داده می‌شود. برای بنرهای دیگر فقط وقتی '
                  'متن کوچک، متن بنر یا متن دکمه را پر کنید.')
    subtitle = models.CharField(max_length=120, blank=True, verbose_name='متن کوچک بالای عنوان',
                                help_text='برای اسلایدر اگر خالی باشد نام سایت نمایش داده می‌شود.')
    description = models.TextField(max_length=400, blank=True, verbose_name='متن بنر')
    button_text = models.CharField(max_length=40, blank=True, verbose_name='متن دکمه',
                                   help_text='برای اسلایدر اگر خالی باشد «مشاهده جزئیات» نمایش داده می‌شود.')
    text_position = models.CharField(choices=BANNER_TEXT_POSITIONS, max_length=10, default='start',
                                     verbose_name='جای متن')
    text_theme = models.CharField(choices=BANNER_TEXT_THEMES, max_length=10, default='light',
                                  verbose_name='رنگ متن')

    # اندازهٔ نمایش
    display_size = models.CharField(choices=BANNER_SIZES, max_length=10, default='auto',
                                    verbose_name='ارتفاع نمایش')
    width = models.CharField(choices=BANNER_WIDTHS, max_length=10, default='default',
                             verbose_name='عرض نمایش',
                             help_text='برای بنرهای کوچک، بزرگ و تک. اسلایدر همیشه تمام‌عرض است.')

    order = models.PositiveIntegerField(default=0, verbose_name='ترتیب نمایش',
                                        help_text='عدد کوچک‌تر زودتر نمایش داده می‌شود.')
    status = models.CharField(choices=STATUS, max_length=10, default='published', verbose_name='وضعیت')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ایجاد')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاریخ به‌روزرسانی')

    class Meta:
        verbose_name = 'بنر'
        verbose_name_plural = 'بنر ها'
        ordering = ['order', '-created_at']

    def banner_image(self):
        return admin_thumbnail(self.image, self.title, width=100, height=50)
    banner_image.short_description = 'تصویر'

    def __str__(self):
        return self.title

    @property
    def is_slider(self):
        return self.banner_type == 'main_slider'

    @property
    def has_overlay(self):
        """آیا متنی روی تصویر نمایش داده شود؟"""
        if not self.show_text:
            return False
        if self.is_slider:
            return True
        return bool(self.subtitle or self.description or self.button_text)

    @property
    def overlay_subtitle(self):
        return self.subtitle

    @property
    def overlay_description(self):
        if self.description:
            return self.description
        return DEFAULT_SLIDER_DESCRIPTION if self.is_slider else ''

    @property
    def overlay_button(self):
        if self.button_text:
            return self.button_text
        return 'مشاهده جزئیات' if (self.is_slider and self.url) else ''

    @property
    def column_class(self):
        if self.width in _BANNER_COLUMNS:
            return _BANNER_COLUMNS[self.width]
        return _BANNER_DEFAULT_COLUMNS.get(self.banner_type, 'col-12')

    @property
    def css_modifiers(self):
        return (
            f'fm-banner--size-{self.display_size} fm-banner--text-{self.text_position} '
            f'fm-banner--theme-{self.text_theme}'
        )


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


class NewsletterSubscriber(models.Model):
    """مشترک خبرنامه — دریافت ایمیل‌های اطلاع‌رسانی فایل‌های جدید و تخفیف‌ها."""

    email = models.EmailField(unique=True, verbose_name='ایمیل')
    is_active = models.BooleanField(default=True, verbose_name='فعال')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ عضویت')

    class Meta:
        verbose_name = 'مشترک خبرنامه'
        verbose_name_plural = 'مشترکان خبرنامه'
        ordering = ['-created_at']

    def __str__(self):
        return self.email


class HtmlBlock(models.Model):
    """بلوک کد HTML قابل‌قرارگیری در بخش‌های ثابت سایت (بنر اطلاع‌رسانی، ویجت و…)."""

    PLACEMENTS = (
        ('site_top', 'همهٔ صفحات — بالای محتوا (زیر هدر)'),
        ('site_bottom', 'همهٔ صفحات — پایین محتوا (بالای فوتر)'),
        ('home_top', 'صفحهٔ اصلی — زیر اسلایدر'),
        ('home_middle', 'صفحهٔ اصلی — وسط صفحه'),
        ('home_bottom', 'صفحهٔ اصلی — پایین صفحه'),
        ('product_bottom', 'همهٔ محصولات — زیر توضیحات'),
        ('article_bottom', 'همهٔ مقاله‌ها — زیر متن مقاله'),
        ('cart_top', 'سبد خرید — بالای صفحه'),
    )

    title = models.CharField(max_length=120, verbose_name='عنوان (فقط برای مدیریت)')
    placement = models.CharField(max_length=30, choices=PLACEMENTS, verbose_name='محل نمایش')
    html = models.TextField(verbose_name='کد HTML',
                            help_text='کد HTML، CSS (<style>) یا JS (<script>) که عیناً اجرا می‌شود.')
    full_width = models.BooleanField(default=False, verbose_name='تمام‌عرض (بدون کادر وسط‌چین)')
    is_active = models.BooleanField(default=True, verbose_name='فعال')
    order = models.PositiveIntegerField(default=0, verbose_name='ترتیب')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ایجاد')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='آخرین تغییر')

    class Meta:
        verbose_name = 'بلوک کد HTML'
        verbose_name_plural = 'بلوک‌های کد HTML'
        ordering = ['placement', 'order', 'id']
        permissions = [
            ('edit_raw_html', 'ویرایش کد HTML خام (اسکریپت‌دار) در محصول، مقاله، صفحه و بلوک‌ها'),
        ]

    def __str__(self):
        return self.title
