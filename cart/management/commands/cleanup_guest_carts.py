"""حذف سبدهای خرید مهمانِ رهاشده و آزاد کردن رزرو کد تخفیف آن‌ها.

هر بازدیدکننده بدون حساب می‌تواند سبد بسازد؛ سبدی که مدت‌ها دست نخورده (نشست
مرورگرش هم منقضی شده) دیگر به کسی نمی‌رسد. اگر چنین سبدی کد تخفیفِ ظرفیت‌دار
رزرو کرده باشد، آن ظرفیت تا ابد مصرف‌شده می‌ماند؛ این دستور رزرو را برمی‌گرداند و
سبد را حذف می‌کند. سفارش‌ها دست نمی‌خورند (فقط ارجاعشان به سبد خالی می‌شود).

اجرای دوره‌ای (مثلاً روزانه با cron):
    python manage.py cleanup_guest_carts --days 14
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from cart.coupons import release_coupon_reservation
from cart.models import Cart


class Command(BaseCommand):
    help = 'حذف سبدهای خرید مهمانِ رهاشده (پیش‌فرض: ۱۴ روز بدون تغییر) و آزاد کردن رزرو کد تخفیف آن‌ها'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=14,
                            help='سبد مهمانی که این تعداد روز تغییر نکرده حذف می‌شود (پیش‌فرض ۱۴ = عمر نشست جنگو).')
        parser.add_argument('--dry-run', action='store_true', help='فقط تعداد را نشان بده.')

    def handle(self, *args, days, dry_run, **options):
        cutoff = timezone.now() - timedelta(days=max(1, days))
        stale = (
            Cart.objects.filter(user__isnull=True, updated_at__lt=cutoff)
            .exclude(items__created_at__gte=cutoff)
            .select_related('coupon')
            .distinct()
        )
        carts = list(stale)
        if dry_run:
            self.stdout.write(f'{len(carts)} سبد مهمانِ رهاشده پیدا شد (چیزی حذف نشد).')
            return
        released = 0
        with transaction.atomic():
            for cart in carts:
                if cart.coupon_id:
                    release_coupon_reservation(cart.coupon)
                    released += 1
            Cart.objects.filter(pk__in=[cart.pk for cart in carts]).delete()
        self.stdout.write(self.style.SUCCESS(
            f'{len(carts)} سبد مهمانِ رهاشده حذف شد؛ رزرو {released} کد تخفیف آزاد شد.'))
