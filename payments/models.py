from django.conf import settings
from django.db import models
from cart.models import Order


class PaymentTransaction(models.Model):
    GATEWAYS = [('zarinpal', 'زرین‌پال'), ('snappay', 'اسنپ‌پی'), ('torobpay', 'ترب‌پی')]
    STATUS = [('created', 'ایجاد شده'), ('redirected', 'ارسال به درگاه'), ('paid', 'موفق'), ('failed', 'ناموفق')]
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='payments', verbose_name='سفارش')
    gateway = models.CharField(max_length=20, choices=GATEWAYS, verbose_name='درگاه')
    authority = models.CharField(max_length=120, blank=True, verbose_name='شناسه درگاه')
    ref_id = models.CharField(max_length=120, blank=True, verbose_name='کد رهگیری')
    amount = models.PositiveBigIntegerField(verbose_name='مبلغ (تومان)')
    status = models.CharField(max_length=12, choices=STATUS, default='created', verbose_name='وضعیت')
    raw_response = models.JSONField(default=dict, blank=True, verbose_name='پاسخ درگاه')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'تراکنش پرداخت'
        verbose_name_plural = 'تراکنش‌های پرداخت'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.order.order_number} - {self.get_gateway_display()}'


class GatewaySettings(models.Model):
    """
    تنظیمات درگاه‌های پرداخت؛ از پنل مدیریت قابل تغییر است.
    اگر فیلدی خالی باشد، مقدار معادل در متغیر محیطی استفاده می‌شود.
    """
    GATEWAY_KEYS = [
        ('zarinpal', 'زرین‌پال (پرداخت مستقیم)'),
        ('snappay', 'اسنپ‌پی'),
        ('torobpay', 'ترب‌پی'),
    ]

    key = models.CharField(max_length=20, choices=GATEWAY_KEYS, unique=True, verbose_name='درگاه')
    title = models.CharField(max_length=100, verbose_name='نام نمایشی در سایت',
                             help_text='مثلاً: پرداخت امن زرین‌پال')
    is_enabled = models.BooleanField(default=False, verbose_name='فعال',
                                     help_text='فقط درگاه‌های فعال در صفحه پرداخت نمایش داده می‌شوند')
    is_sandbox = models.BooleanField(default=False, verbose_name='حالت تست (سندباکس)',
                                     help_text='برای آزمایش فرآیند پرداخت بدون حساب واقعی (فقط زرین‌پال)')
    merchant_id = models.CharField(max_length=120, blank=True, verbose_name='مرچنت کد / شناسه درگاه',
                                   help_text='زرین‌پال و ترب‌پی')
    client_id = models.CharField(max_length=120, blank=True, verbose_name='Client ID', help_text='اسنپ‌پی')
    client_secret = models.CharField(max_length=250, blank=True, verbose_name='Client Secret', help_text='اسنپ‌پی')
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
    def is_configured(self):
        """آیا اطلاعات اعتباری لازم این درگاه ثبت شده است؟"""
        if self.key in ('zarinpal', 'torobpay'):
            return bool(self.merchant_id)
        if self.key == 'snappay':
            return bool(self.client_id and self.client_secret)
        return False

    def effective_credentials(self):
        """اعتبارنامه‌ها: اول دیتابیس، بعد متغیر محیطی."""
        env_fallback = {
            'zarinpal': {'merchant_id': getattr(settings, 'ZARINPAL_MERCHANT_ID', '')},
            'snappay': {'client_id': getattr(settings, 'SNAPPAY_CLIENT_ID', ''),
                        'client_secret': getattr(settings, 'SNAPPAY_CLIENT_SECRET', '')},
            'torobpay': {'merchant_id': getattr(settings, 'TOROBPAY_MERCHANT_ID', '')},
        }.get(self.key, {})

        return {
            'merchant_id': self.merchant_id or env_fallback.get('merchant_id', ''),
            'client_id': self.client_id or env_fallback.get('client_id', ''),
            'client_secret': self.client_secret or env_fallback.get('client_secret', ''),
        }
