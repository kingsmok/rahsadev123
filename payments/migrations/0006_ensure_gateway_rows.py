"""ردیف تنظیمات درگاه‌های اقساطی را (غیرفعال) می‌سازد تا مدیر فقط اطلاعات را وارد کند.

ردیف‌های موجود دست نمی‌خورند. ردیف زرین‌پال مثل قبل با seed_demo (فعال) یا از
پنل مدیریت ساخته می‌شود؛ اگر این مایگریشن آن را غیرفعال می‌ساخت، get_or_create
در seed_demo دیگر زرین‌پال را در نصب تازه فعال نمی‌کرد.
"""
from django.db import migrations

ROWS = (
    ('zarinplus', 'زرین‌پلاس — خرید اقساطی', 'خرید اقساطی با اعتبار زرین‌پلاس', 1),
    ('snappay', 'اسنپ‌پی — خرید اقساطی', 'خرید اقساطی؛ ۴ قسط بدون بهره با اسنپ‌پی', 2),
    ('torobpay', 'ترب‌پی — خرید اعتباری', 'خرید اعتباری و اقساطی با ترب‌پی', 3),
)


def ensure_rows(apps, schema_editor):
    GatewaySettings = apps.get_model('payments', 'GatewaySettings')
    for key, title, description, order in ROWS:
        GatewaySettings.objects.get_or_create(
            key=key,
            defaults={'title': title, 'description': description, 'order': order, 'is_enabled': False},
        )


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0005_installment_gateways'),
    ]

    operations = [
        migrations.RunPython(ensure_rows, migrations.RunPython.noop),
    ]
