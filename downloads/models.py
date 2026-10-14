from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils import timezone
from datetime import timedelta
from shortuuid.django_fields import ShortUUIDField

from cart.models import Order
from product.models import Product


#: Order statuses meaning the money went back to the customer.  A token whose
#: order is in one of these must stop serving the file — otherwise buying a
#: product, downloading it and asking for a refund within the return window
#: keeps both the file and the money.  Every download path (the token link, the
#: legacy per-product URL, the product page) relies on this one definition.
REVOKED_ORDER_STATUSES = frozenset({'cancelled', 'refunded'})


class DownloadTokenQuerySet(models.QuerySet):
    def entitled(self):
        """Tokens whose order still grants access to the file."""
        return self.exclude(order__status__in=REVOKED_ORDER_STATUSES)


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

    objects = DownloadTokenQuerySet.as_manager()

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
    def remaining_downloads(self):
        return max(0, self.max_downloads - self.download_count)

    @property
    def is_revoked(self):
        """The order was cancelled or refunded, so the entitlement is withdrawn."""
        return self.order.status in REVOKED_ORDER_STATUSES

    @property
    def is_valid(self):
        return (
            self.is_active
            and not self.is_expired
            and self.download_count < self.max_downloads
            and not self.is_revoked
        )

    def register_download(self):
        """Atomically consume one permitted download.

        Checking ``is_valid`` and incrementing in separate queries allowed two
        simultaneous requests to pass the final-download check.  Keep the
        validity predicates in the update itself, so the download ceiling is
        enforced by the database as well as the view.
        """
        now = timezone.now()
        # ``entitled()`` keeps the refund rule inside the same atomic UPDATE,
        # so no caller can consume a download for a cancelled/refunded order.
        consumed = DownloadToken.objects.entitled().filter(
            pk=self.pk,
            is_active=True,
            download_count__lt=F('max_downloads'),
        ).filter(
            Q(expires_at__isnull=True) | Q(expires_at__gte=now)
        ).update(download_count=F('download_count') + 1)

        if consumed:
            self.refresh_from_db(fields=['download_count'])
        return bool(consumed)
