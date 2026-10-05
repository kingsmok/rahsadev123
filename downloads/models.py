from django.conf import settings
from django.db import models
from django.utils import timezone
from datetime import timedelta
from shortuuid.django_fields import ShortUUIDField

from cart.models import Order
from product.models import Product


class DownloadToken(models.Model):
    token = ShortUUIDField(
        length=32, max_length=40, unique=True, editable=False,
        verbose_name='توکن دانلود',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='download_tokens', verbose_name='کاربر',
    )
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE,
        related_name='download_tokens', verbose_name='محصول',
    )
    order = models.ForeignKey(
        Order, on_delete=models.CASCADE,
        related_name='download_tokens', verbose_name='سفارش',
    )
    max_downloads = models.PositiveIntegerField(default=5, verbose_name='حداکثر تعداد دانلود')
    download_count = models.PositiveIntegerField(default=0, editable=False, verbose_name='تعداد دانلود انجام شده')
    is_active = models.BooleanField(default=True, verbose_name='فعال')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ایجاد')
    expires_at = models.DateTimeField(null=True, blank=True, verbose_name='تاریخ انقضا')

    class Meta:
        verbose_name = 'توکن دانلود'
        verbose_name_plural = 'توکن‌های دانلود'
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(days=7)
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.product.title} - {self.user.username}'

    @property
    def is_expired(self):
        return bool(self.expires_at and timezone.now() > self.expires_at)

    @property
    def is_valid(self):
        return self.is_active and not self.is_expired and self.download_count < self.max_downloads

    def register_download(self):
        self.download_count = models.F('download_count') + 1
        self.save(update_fields=['download_count'])
        self.refresh_from_db(fields=['download_count'])
