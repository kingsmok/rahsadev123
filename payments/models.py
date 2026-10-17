from django.conf import settings
from django.db import models
from cart.models import Order


class PaymentTransactionQuerySet(models.QuerySet):
    def unfulfilled(self):
        """Verified (the customer WAS charged) but not deliverable: the refund queue."""
        return self.filter(status='failed', raw_response__unfulfilled=True)

    def declined(self):
        """Failed attempts in which no money was taken.

        Not ``exclude(raw_response__unfulfilled=True)``: for rows without that
        key the JSON comparison is NULL, so the negation drops *every* row
        (verified on SQLite).  A primary-key subquery is exact on any backend.
        """
        return self.filter(status='failed').exclude(
            pk__in=self.model.objects.unfulfilled().values('pk'),
        )


class PaymentTransaction(models.Model):
    GATEWAYS = [
        ('zarinpal', 'زرین‌پال'), ('zarinplus', 'زرین‌پلاس (اقساطی)'),
        ('snappay', 'اسنپ‌پی (اقساطی)'), ('torobpay', 'ترب‌پی (اقساطی)'),
        # سفارشی که کد تخفیف کل مبلغش را پوشش داده؛ هیچ درگاهی درگیر نیست.
        ('free', 'سفارش رایگان (بدون درگاه)'),
    ]
    STATUS = [('created', 'ایجاد شده'), ('redirected', 'ارسال به درگاه'), ('paid', 'موفق'), ('failed', 'ناموفق')]
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='payments', verbose_name='سفارش')
    gateway = models.CharField(max_length=20, choices=GATEWAYS, verbose_name='درگاه')
    authority = models.CharField(max_length=255, blank=True, verbose_name='شناسه درگاه')
    # شناسهٔ یکتایی که فروشگاه برای هر تلاش پرداخت به درگاه‌های اقساطی
    # (اسنپ‌پی/ترب‌پی: transactionId) می‌فرستد و در بازگشت با آن تطبیق می‌دهد.
    reference_id = models.CharField(max_length=64, blank=True, db_index=True, verbose_name='شناسه ارسالی به درگاه')
    ref_id = models.CharField(max_length=120, blank=True, verbose_name='کد رهگیری')
    amount = models.PositiveBigIntegerField(verbose_name='مبلغ (تومان)')
    status = models.CharField(max_length=12, choices=STATUS, default='created', verbose_name='وضعیت')
    raw_response = models.JSONField(default=dict, blank=True, verbose_name='پاسخ درگاه')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = PaymentTransactionQuerySet.as_manager()

    class Meta:
        verbose_name = 'تراکنش پرداخت'
        verbose_name_plural = 'تراکنش‌های پرداخت'
        ordering = ['-created_at']
        constraints = [
            # Empty is the normal value before a gateway returns an authority;
            # once present, a provider reference must identify one transaction.
            models.UniqueConstraint(
                fields=['authority'],
                condition=models.Q(authority__gt=''),
                name='payment_transaction_unique_authority',
            ),
        ]

    def __str__(self):
        return f'{self.order.order_number} - {self.get_gateway_display()}'


class GatewaySettings(models.Model):
    """
    تنظیمات درگاه‌های پرداخت؛ از پنل مدیریت قابل تغییر است.
    اگر فیلدی خالی باشد، مقدار معادل در متغیر محیطی استفاده می‌شود.
    """
    GATEWAY_KEYS = [
        ('zarinpal', 'زرین‌پال (پرداخت مستقیم)'),
        ('zarinplus', 'زرین‌پلاس (خرید اقساطی زرین‌پال)'),
        ('snappay', 'اسنپ‌پی (خرید اقساطی)'),
        ('torobpay', 'ترب‌پی (خرید اعتباری/اقساطی)'),
    ]
    INSTALLMENT_KEYS = ('zarinplus', 'snappay', 'torobpay')
    LOGOS = {
        'zarinpal': 'img/payments/zarinpal.svg',
        'zarinplus': 'img/payments/zarinplus.png',
        'snappay': 'img/payments/snapppay.svg',
        'torobpay': 'img/payments/torobpay.svg',
    }
    DEFAULT_DESCRIPTIONS = {
        'zarinpal': 'پرداخت امن با همهٔ کارت‌های عضو شتاب',
        'zarinplus': 'خرید اقساطی با اعتبار زرین‌پلاس',
        'snappay': 'خرید اقساطی؛ ۴ قسط بدون بهره با اسنپ‌پی',
        'torobpay': 'خرید اعتباری و اقساطی با ترب‌پی',
    }

    key = models.CharField(max_length=20, choices=GATEWAY_KEYS, unique=True, verbose_name='درگاه')
    title = models.CharField(max_length=100, verbose_name='نام نمایشی در سایت',
                             help_text='مثلاً: پرداخت امن زرین‌پال')
    is_enabled = models.BooleanField(default=False, verbose_name='فعال',
                                     help_text='فقط درگاه‌های فعال در صفحه پرداخت نمایش داده می‌شوند')
    is_sandbox = models.BooleanField(default=False, verbose_name='حالت تست (سندباکس)',
                                     help_text='زرین‌پال: سندباکس رسمی. اسنپ‌پی: اگر آدرس API خالی باشد، سرور staging استفاده می‌شود.')
    merchant_id = models.CharField(max_length=120, blank=True, verbose_name='مرچنت کد / توکن پذیرنده',
                                   help_text='زرین‌پال: مرچنت کد ۳۶ کاراکتری. زرین‌پلاس: توکن پذیرنده (Merchant Token).')
    client_id = models.CharField(max_length=120, blank=True, verbose_name='Client ID', help_text='اسنپ‌پی و ترب‌پی')
    client_secret = models.CharField(max_length=250, blank=True, verbose_name='Client Secret', help_text='اسنپ‌پی و ترب‌پی')
    username = models.CharField(max_length=150, blank=True, verbose_name='نام کاربری API',
                                help_text='اسنپ‌پی و ترب‌پی (از پنل/تیکت پذیرندگی)')
    password = models.CharField(max_length=250, blank=True, verbose_name='رمز عبور API', help_text='اسنپ‌پی و ترب‌پی')
    api_base_url = models.CharField(
        max_length=255, blank=True, verbose_name='آدرس پایهٔ API',
        help_text='اسنپ‌پی: آدرسی که اسنپ‌پی هنگام قرارداد می‌دهد (اجباری در حالت عملیاتی). '
                  'ترب‌پی: اگر خالی باشد https://cpg.torobpay.com')
    service_slug = models.CharField(max_length=50, blank=True, verbose_name='شناسهٔ سرویس',
                                    help_text='فقط زرین‌پلاس؛ پیش‌فرض zarinplus')
    description = models.CharField(max_length=255, blank=True, verbose_name='توضیح کوتاه برای سایت')
    order = models.PositiveIntegerField(default=0, verbose_name='ترتیب نمایش')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='آخرین تغییر')

    class Meta:
        verbose_name = 'تنظیمات درگاه پرداخت'
        verbose_name_plural = 'تنظیمات درگاه‌های پرداخت'
        ordering = ['order', 'key']

    def __str__(self):
        return self.title or self.get_key_display()

    @property
    def is_installment(self):
        return self.key in self.INSTALLMENT_KEYS

    @property
    def logo_static_path(self):
        return self.LOGOS.get(self.key, 'img/ico/png-10.png')

    @property
    def display_description(self):
        return self.description or self.DEFAULT_DESCRIPTIONS.get(self.key, 'پرداخت امن از طریق کارت‌های عضو شتاب')

    @property
    def is_configured(self):
        """Whether database *or environment* credentials are complete."""
        credentials = self.effective_credentials()
        if self.key in ('zarinpal', 'zarinplus'):
            return bool(credentials['merchant_id'])
        if self.key == 'snappay':
            return bool(credentials['client_id'] and credentials['client_secret'] and credentials['username']
                        and credentials['password'] and (credentials['api_base_url'] or self.is_sandbox))
        if self.key == 'torobpay':
            return bool(credentials['client_id'] and credentials['client_secret'] and credentials['username']
                        and credentials['password'])
        return False

    @property
    def is_implemented(self):
        """آیا آداپتر این درگاه واقعاً به API آن وصل است؟"""
        from .services import GATEWAYS

        adapter = GATEWAYS.get(self.key)
        return bool(adapter and getattr(adapter, 'implemented', False))

    @property
    def is_available(self):
        """قابل پیشنهاد به مشتری: فعال + پیکربندی‌شده + پیاده‌سازی‌شده."""
        return self.is_enabled and self.is_configured and self.is_implemented

    def effective_credentials(self):
        """اعتبارنامه‌ها: اول دیتابیس، بعد متغیر محیطی."""
        env = lambda name: getattr(settings, name, '')  # noqa: E731
        env_fallback = {
            'zarinpal': {'merchant_id': env('ZARINPAL_MERCHANT_ID')},
            'zarinplus': {'merchant_id': env('ZARINPLUS_MERCHANT_TOKEN')},
            'snappay': {'client_id': env('SNAPPAY_CLIENT_ID'), 'client_secret': env('SNAPPAY_CLIENT_SECRET'),
                        'username': env('SNAPPAY_USERNAME'), 'password': env('SNAPPAY_PASSWORD'),
                        'api_base_url': env('SNAPPAY_BASE_URL')},
            'torobpay': {'merchant_id': env('TOROBPAY_MERCHANT_ID'),
                         'client_id': env('TOROBPAY_CLIENT_ID'), 'client_secret': env('TOROBPAY_CLIENT_SECRET'),
                         'username': env('TOROBPAY_USERNAME'), 'password': env('TOROBPAY_PASSWORD'),
                         'api_base_url': env('TOROBPAY_BASE_URL')},
        }.get(self.key, {})

        return {
            'merchant_id': self.merchant_id or env_fallback.get('merchant_id', ''),
            'client_id': self.client_id or env_fallback.get('client_id', ''),
            'client_secret': self.client_secret or env_fallback.get('client_secret', ''),
            'username': self.username or env_fallback.get('username', ''),
            'password': self.password or env_fallback.get('password', ''),
            'api_base_url': (self.api_base_url or env_fallback.get('api_base_url', '')).strip().rstrip('/'),
            'service_slug': self.service_slug or 'zarinplus',
        }
