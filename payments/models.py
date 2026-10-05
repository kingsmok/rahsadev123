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
