import secrets

from django.core.exceptions import ValidationError
from django.db import models
from django.contrib.auth.models import User
from shortuuid.django_fields import ShortUUIDField
from product.models import Product
from django.utils import timezone


class Coupon(models.Model):
    DISCOUNT_TYPE = (
        ('percentage', 'درصدی'),
        ('fixed', 'مبلغ ثابت')
    )

    code = models.CharField(max_length=20, unique=True, verbose_name='کد تخفیف')
    discount_type = models.CharField(max_length=10, choices=DISCOUNT_TYPE, verbose_name='نوع تخفیف')
    discount_value = models.IntegerField(verbose_name='مقدار تخفیف')
    max_usage = models.IntegerField(null=True, blank=True, verbose_name='حداکثر استفاده')
    usage_count = models.IntegerField(default=0, verbose_name='تعداد استفاده شده')
    valid_from = models.DateTimeField(default=timezone.now, verbose_name='معتبر از')
    valid_to = models.DateTimeField(verbose_name='معتبر تا')
    is_active = models.BooleanField(default=True, verbose_name='فعال')
    minimum_order_amount = models.PositiveIntegerField(default=0, verbose_name='حداقل مبلغ سفارش')
    maximum_discount = models.PositiveIntegerField(null=True, blank=True, verbose_name='سقف تخفیف')
    per_user_limit = models.PositiveIntegerField(default=0, verbose_name='محدودیت برای هر کاربر')

    class Meta:
        verbose_name = 'کوپن تخفیف'
        verbose_name_plural = 'کوپن ‌های تخفیف'
        constraints = [
            models.CheckConstraint(
                condition=models.Q(discount_value__gte=0),
                name='coupon_discount_value_nonnegative',
            ),
            models.CheckConstraint(
                condition=models.Q(usage_count__gte=0),
                name='coupon_usage_count_nonnegative',
            ),
        ]

    def __str__(self):
        return self.code

    def clean(self):
        # Customers type codes in any case and checkout looks them up with
        # ``code__iexact``; "WELCOME10" next to "welcome10" made that lookup
        # raise MultipleObjectsReturned (HTTP 500).  ``unique=True`` alone is
        # case-sensitive, so reject case-insensitive duplicates here.
        super().clean()
        if self.code and Coupon.objects.filter(code__iexact=self.code).exclude(pk=self.pk).exists():
            raise ValidationError({'code': 'این کد تخفیف (بدون توجه به حروف بزرگ و کوچک) قبلاً ثبت شده است.'})

    def is_valid(self):
        """Whether a *new* reservation of this coupon may be taken now.

        Pure check, no writes.  It used to set ``is_active=False`` and call a
        full ``save()`` once ``max_usage`` was reached: that overwrote
        concurrent ``usage_count`` updates and, because cart revalidation
        requires ``is_active``, stripped the discount from carts whose
        reservation had already been counted.
        """
        now = timezone.now()
        if not self.is_active:
            return False
        if self.max_usage and self.usage_count >= self.max_usage:
            return False
        return self.valid_from <= now <= self.valid_to


class Cart(models.Model):
    # خالی = سبد خرید مهمان: خرید بدون ثبت‌نام. شناسهٔ آن در نشست مرورگر
    # (سمت سرور) نگه داشته می‌شود و با ورود به حساب، در سبد همان حساب ادغام می‌شود.
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='cart', null=True, blank=True,
                                verbose_name='کاربر', help_text='خالی = سبد خرید مهمان (بدون حساب کاربری)')
    coupon = models.ForeignKey(Coupon, null=True, blank=True, on_delete=models.SET_NULL, verbose_name='کوپن تخفیف')
    coupon_discount = models.IntegerField(default=0, verbose_name='مقدار تخفیف اعمال شده')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ایجاد')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاریخ به‌روزرسانی')

    class Meta:
        verbose_name = 'سبد خرید'
        verbose_name_plural = 'سبد های خرید'

    def __str__(self):
        if self.user_id:
            return f"سبد خرید {self.user.username}"
        return f"سبد خرید مهمان #{self.pk}"

    @property
    def is_guest(self):
        return self.user_id is None

    @property
    def total_price(self):
        return sum(item.total_price for item in self.items.all())

    @property
    def final_price(self):
        # Coupon data can be changed through the admin after it is applied;
        # never expose a negative payable amount if stale data exists.
        return max(0, self.total_price - self.coupon_discount)

    def clear(self):
        self.items.all().delete()
        self.coupon = None
        self.coupon_discount = 0
        self.save()


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items', verbose_name='سبد خرید')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name='محصول')
    quantity = models.PositiveIntegerField(default=1, verbose_name='تعداد',
                                           help_text='برای محصولات دانلودی عدد ۱ ثبت می‌شود')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ایجاد')

    class Meta:
        verbose_name = 'آیتم سبد خرید'
        verbose_name_plural = 'آیتم‌ های سبد خرید'
        ordering = ['-created_at', '-id']
        unique_together = ['cart', 'product']
        constraints = [
            # فروشگاه فقط فایل دیجیتال می‌فروشد؛ کنترل تعداد در UI گمراه‌کننده
            # است، پس این قاعده در دیتابیس هم تضمین می‌شود.
            models.CheckConstraint(
                condition=models.Q(quantity=1),
                name='cart_item_quantity_exactly_one',
            ),
        ]

    def __str__(self):
        return f"{self.product.title} ({self.quantity})"

    @property
    def total_price(self):
        return self.product.price * self.quantity


class OrderItem(models.Model):
    order = models.ForeignKey('Order', on_delete=models.CASCADE, related_name='order_items', verbose_name='سفارش')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='order_items', verbose_name='محصول')
    title_snapshot = models.CharField(max_length=300, verbose_name='عنوان هنگام خرید')
    unit_price = models.PositiveIntegerField(verbose_name='قیمت واحد')
    quantity = models.PositiveIntegerField(default=1)
    total_price = models.PositiveIntegerField(verbose_name='مجموع')
    class Meta:
        verbose_name='آیتم سفارش'; verbose_name_plural='آیتم‌های سفارش'
        indexes=[models.Index(fields=['product']), models.Index(fields=['order'])]
        constraints = [
            models.UniqueConstraint(
                fields=['order', 'product'],
                name='order_item_unique_product_per_order',
            ),
        ]

class Order(models.Model):
    ORDER_STATUS = (
        ('pending', 'در انتظار پرداخت'),
        ('paid', 'پرداخت شده - آماده دانلود'),
        ('processing', 'در حال پردازش'),
        ('shipped', 'ارسال شده'),
        ('delivered', 'تحویل داده شده'),
        ('cancelled', 'لغو شده'),
    )

    #: A digital order is delivered the moment it is paid (download tokens are
    #: issued in the same transaction); ``delivered`` remains for legacy rows.
    COMPLETED_STATUSES = ('paid', 'delivered')

    # خالی = خرید مهمان. چنین سفارشی فقط با نشست همان مرورگر یا لینک محرمانهٔ
    # «access_token» (صفحهٔ پیگیری سفارش) باز می‌شود؛ ساخت یا ورود به حساب با
    # تأیید مالکیت، آن را به حساب منتقل می‌کند (cart.guest.attach_orders).
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders', null=True, blank=True,
                             verbose_name='کاربر', help_text='خالی = خرید مهمان (بدون ثبت‌نام)')
    order_number = ShortUUIDField(length=10, max_length=10, alphabet="1234567890", unique=True, verbose_name="شماره سفارش")
    cart = models.ForeignKey(Cart, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='سبد خرید')
    items_data = models.JSONField(null=True, blank=True, verbose_name='اطلاعات محصولات')
    total_price = models.IntegerField(verbose_name='مبلغ کل')
    coupon_discount = models.IntegerField(default=0, verbose_name='تخفیف کوپن')
    shipping_cost = models.IntegerField(default=0, verbose_name='هزینه ارسال (محصولات دیجیتال: صفر)')
    final_price = models.IntegerField(verbose_name='مبلغ قابل پرداخت')
    status = models.CharField(max_length=20, choices=ORDER_STATUS, default='pending', verbose_name='وضعیت سفارش')
    # اطلاعات تماسی که خریدار هنگام پرداخت وارد کرده است (برای خرید مهمان
    # ضروری است؛ برای سفارش اعضا فقط یک عکس فوری از پروفایل برای پشتیبانی).
    contact_mobile = models.CharField(max_length=11, blank=True, db_index=True, verbose_name='موبایل خریدار')
    contact_email = models.EmailField(max_length=254, blank=True, verbose_name='ایمیل خریدار')
    access_token = models.CharField(
        max_length=64, unique=True, null=True, blank=True, editable=False,
        verbose_name='کلید محرمانهٔ پیگیری (خرید مهمان)',
        help_text='فقط برای سفارش مهمان ساخته می‌شود؛ لینک صفحهٔ سفارش و دانلود بدون حساب کاربری.')
    create_account_requested = models.BooleanField(
        default=False, verbose_name='خریدار ساخت حساب را انتخاب کرد',
        help_text='رضایت صریح خریدار مهمان برای ساخت حساب با همین اطلاعات پس از پرداخت.')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ایجاد')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاریخ به‌روزرسانی')

    class Meta:
        verbose_name = 'سفارش'
        verbose_name_plural = 'سفارشات'
        ordering = ['-created_at']

    def __str__(self):
        return f"سفارش {self.order_number} - {self.customer_label}"

    @property
    def is_guest(self):
        return self.user_id is None

    @property
    def customer_label(self):
        """Who placed the order, for staff screens (never shown to other customers)."""
        if self.user_id:
            return self.user.get_username()
        contact = self.contact_mobile or self.contact_email or 'بدون اطلاعات تماس'
        return f'مهمان ({contact})'

    def save(self, *args, **kwargs):
        if self.user_id is None and not self.access_token:
            # 256 بیت تصادفی؛ حدس‌زدنی نیست و ستون یکتا تصادم را هم رد می‌کند.
            self.access_token = secrets.token_urlsafe(32)
        if self.cart and not self.items_data:
            self.items_data = {
                'items': [{
                    'product_id': item.product.id,
                    'title': item.product.title,
                    'quantity': item.quantity,
                    'price': item.product.price
                } for item in self.cart.items.select_related('product')],
                'coupon': self.cart.coupon.code if self.cart.coupon else None,
                'discount': self.cart.coupon_discount
            }
        super().save(*args, **kwargs)
