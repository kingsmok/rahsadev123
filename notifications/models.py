"""اعلان‌های مدیریت و تنظیمات ارتباطی (ایمیل SMTP و پیامک sms.ir).

رمز SMTP و کلید API پیامک در دیتابیس نگهداری می‌شوند تا مدیر بدون دسترسی به
سرور آن‌ها را تنظیم کند؛ فرم‌های ادمین این مقادیر را هرگز دوباره در صفحه
نمایش نمی‌دهند (فقط «تنظیم شده/نشده») و خالی گذاشتن فیلد مقدار قبلی را حفظ
می‌کند. مقادیر محیطی (EMAIL_HOST_PASSWORD و …) همچنان پشتیبان هستند.
"""
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class SingletonModel(models.Model):
    """A settings table that always has exactly one row (pk=1)."""

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):  # pragma: no cover - guarded in admin too
        return 0, {}

    @classmethod
    def load(cls):
        obj = cls.objects.filter(pk=1).first()
        if obj is None:
            obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class AdminNotification(models.Model):
    KINDS = (
        ('order_paid', 'سفارش پرداخت‌شده'),
        ('service_request', 'درخواست طراحی سایت'),
        ('consultation', 'درخواست مشاوره'),
        ('contact', 'پیام تماس با ما'),
        ('comment', 'دیدگاه در انتظار تأیید'),
        ('user_registered', 'ثبت‌نام کاربر جدید'),
        ('payment_problem', 'مشکل پرداخت'),
        ('system', 'سیستمی'),
    )
    LEVELS = (
        ('info', 'اطلاع'),
        ('success', 'موفق'),
        ('warning', 'هشدار'),
        ('danger', 'فوری'),
    )
    ICONS = {
        'order_paid': 'fa-bag-shopping',
        'service_request': 'fa-laptop-code',
        'consultation': 'fa-headset',
        'contact': 'fa-envelope',
        'comment': 'fa-comment-dots',
        'user_registered': 'fa-user-plus',
        'payment_problem': 'fa-triangle-exclamation',
        'system': 'fa-gear',
    }

    kind = models.CharField(max_length=30, choices=KINDS, verbose_name='نوع')
    level = models.CharField(max_length=10, choices=LEVELS, default='info', verbose_name='اهمیت')
    title = models.CharField(max_length=200, verbose_name='عنوان')
    message = models.TextField(blank=True, verbose_name='شرح')
    url = models.CharField(max_length=500, blank=True, verbose_name='لینک بررسی')
    # Prevents a duplicate alert when the same event is signalled twice
    # (e.g. an order saved as paid again by staff).
    dedupe_key = models.CharField(max_length=120, blank=True, db_index=True, verbose_name='کلید یکتا')
    is_read = models.BooleanField(default=False, db_index=True, verbose_name='خوانده شده')
    read_at = models.DateTimeField(null=True, blank=True, verbose_name='زمان خواندن')
    read_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                related_name='+', verbose_name='خوانده شده توسط')
    emailed = models.BooleanField(default=False, verbose_name='ایمیل ارسال شد')
    sms_sent = models.BooleanField(default=False, verbose_name='پیامک ارسال شد')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='زمان')

    class Meta:
        verbose_name = 'اعلان مدیریت'
        verbose_name_plural = 'اعلان‌های مدیریت'
        ordering = ['-created_at', '-id']

    def __str__(self):
        return self.title

    @property
    def icon(self):
        return self.ICONS.get(self.kind, 'fa-bell')

    def mark_read(self, user=None):
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.read_by = user if (user and user.is_authenticated) else None
            self.save(update_fields=['is_read', 'read_at', 'read_by'])


class EmailSettings(SingletonModel):
    SECURITY = (
        ('tls', 'STARTTLS (معمولاً پورت 587)'),
        ('ssl', 'SSL/TLS (معمولاً پورت 465)'),
        ('none', 'بدون رمزنگاری (معمولاً پورت 25 — توصیه نمی‌شود)'),
    )

    is_enabled = models.BooleanField(
        default=False, verbose_name='استفاده از این تنظیمات SMTP',
        help_text='اگر غیرفعال باشد، تنظیمات سرور (متغیرهای محیطی EMAIL_*) استفاده می‌شود.')
    host = models.CharField(max_length=255, blank=True, verbose_name='آدرس سرور SMTP',
                            help_text='مثلاً mail.yourdomain.ir (از پنل هاست، بخش Email Accounts)')
    port = models.PositiveIntegerField(default=587, validators=[MinValueValidator(1), MaxValueValidator(65535)],
                                       verbose_name='پورت')
    security = models.CharField(max_length=10, choices=SECURITY, default='tls', verbose_name='رمزنگاری')
    username = models.CharField(max_length=255, blank=True, verbose_name='نام کاربری',
                                help_text='معمولاً همان آدرس کامل ایمیل، مثلاً info@yourdomain.ir')
    password = models.CharField(max_length=255, blank=True, verbose_name='رمز عبور ایمیل')
    from_email = models.EmailField(blank=True, verbose_name='آدرس فرستنده',
                                   help_text='اگر خالی باشد نام کاربری استفاده می‌شود.')
    from_name = models.CharField(max_length=100, blank=True, verbose_name='نام فرستنده',
                                 help_text='اگر خالی باشد نام سایت استفاده می‌شود.')
    timeout = models.PositiveSmallIntegerField(default=15, validators=[MinValueValidator(3), MaxValueValidator(120)],
                                               verbose_name='مهلت اتصال (ثانیه)')

    admin_recipients = models.TextField(
        blank=True, verbose_name='ایمیل مدیران برای دریافت اعلان‌ها',
        help_text='هر ایمیل در یک خط یا جداشده با ویرگول. خالی = بدون ارسال ایمیل اعلان.')
    notify_order_paid = models.BooleanField(default=True, verbose_name='ایمیل برای سفارش پرداخت‌شده')
    notify_service_request = models.BooleanField(default=True, verbose_name='ایمیل برای درخواست طراحی سایت/مشاوره')
    notify_contact = models.BooleanField(default=True, verbose_name='ایمیل برای پیام تماس با ما')
    notify_comment = models.BooleanField(default=False, verbose_name='ایمیل برای دیدگاه جدید')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='آخرین تغییر')

    class Meta:
        verbose_name = 'تنظیمات ایمیل (SMTP)'
        verbose_name_plural = 'تنظیمات ایمیل (SMTP)'

    def __str__(self):
        return 'تنظیمات ایمیل (SMTP)'

    @property
    def is_usable(self):
        return bool(self.is_enabled and self.host)

    @property
    def sender(self):
        from email.utils import formataddr

        address = self.from_email or self.username
        if not address:
            return ''
        if self.from_name:
            return formataddr((self.from_name, address))
        return address

    def recipient_list(self):
        raw = (self.admin_recipients or '').replace('،', ',').replace('\n', ',')
        return [item.strip() for item in raw.split(',') if item.strip()]


class SmsSettings(SingletonModel):
    is_enabled = models.BooleanField(default=False, verbose_name='فعال‌سازی پیامک (sms.ir)')
    api_key = models.CharField(max_length=255, blank=True, verbose_name='کلید API (X-API-KEY)',
                               help_text='از پنل sms.ir: برنامه‌نویسان ← لیست کلیدهای API. '
                                         'برای آزمایش می‌توانید کلید «سندباکس» بسازید.')
    line_number = models.CharField(max_length=20, blank=True, verbose_name='شماره خط ارسال',
                                   help_text='برای پیامک‌های متنی اعلان مدیر (ارسال گروهی). برای کد تأیید لازم نیست.')

    otp_login_enabled = models.BooleanField(default=False, verbose_name='ورود و ثبت‌نام با کد پیامکی')
    otp_template_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='شناسه قالب کد تأیید',
        help_text='قالب «ارسال سریع» در پنل sms.ir، مثلاً «کد ورود شما: #CODE#». در سندباکس: 123456')
    otp_parameter = models.CharField(max_length=30, default='CODE', verbose_name='نام متغیر کد در قالب',
                                     help_text='بدون #؛ برای قالب «کد ورود شما: #CODE#» مقدار CODE است.')
    otp_length = models.PositiveSmallIntegerField(default=5, validators=[MinValueValidator(4), MaxValueValidator(8)],
                                                  verbose_name='تعداد رقم کد')
    otp_ttl_seconds = models.PositiveSmallIntegerField(default=120, validators=[MinValueValidator(60), MaxValueValidator(600)],
                                                       verbose_name='اعتبار کد (ثانیه)')

    admin_mobiles = models.TextField(blank=True, verbose_name='موبایل مدیران برای اعلان‌ها',
                                     help_text='هر شماره در یک خط یا جداشده با ویرگول، مثلاً 09121234567.')
    alert_template_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='شناسه قالب اعلان مدیر (اختیاری)',
        help_text='اگر تنظیم شود، اعلان با «ارسال سریع» و متغیرهای TITLE و DETAIL فرستاده می‌شود؛ '
                  'وگرنه با شماره خط بالا به صورت متنی.')
    notify_order_paid = models.BooleanField(default=True, verbose_name='پیامک برای سفارش پرداخت‌شده')
    notify_service_request = models.BooleanField(default=True, verbose_name='پیامک برای درخواست طراحی سایت/مشاوره')
    notify_contact = models.BooleanField(default=False, verbose_name='پیامک برای پیام تماس با ما')
    notify_comment = models.BooleanField(default=False, verbose_name='پیامک برای دیدگاه جدید')

    customer_order_template_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='شناسه قالب پیامک خرید موفق به مشتری (اختیاری)',
        help_text='متغیرها: ORDER (شماره سفارش) و AMOUNT (مبلغ به تومان).')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='آخرین تغییر')

    class Meta:
        verbose_name = 'تنظیمات پیامک (sms.ir)'
        verbose_name_plural = 'تنظیمات پیامک (sms.ir)'

    def __str__(self):
        return 'تنظیمات پیامک (sms.ir)'

    @property
    def is_usable(self):
        return bool(self.is_enabled and self.api_key)

    @property
    def otp_available(self):
        return bool(self.is_usable and self.otp_login_enabled and self.otp_template_id and self.otp_parameter)

    def admin_mobile_list(self):
        raw = (self.admin_mobiles or '').replace('،', ',').replace('\n', ',')
        return [item.strip() for item in raw.split(',') if item.strip()]
