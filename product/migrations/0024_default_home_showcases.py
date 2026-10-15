"""ویترین‌های پیش‌فرض صفحهٔ اصلی (قابل تغییر در پنل مدیریت).

همان رفتار قبلی صفحهٔ اصلی را بازسازی می‌کند، با یک اصلاح: اسلایدر کوچک کنار
«پیشنهادهای ویژه» حالا جدیدترین محصولات را نشان می‌دهد؛ قبلاً فقط محصولات
بدون قیمت قبلی را نشان می‌داد و وقتی همهٔ محصولات تخفیف داشتند خالی بود.
"""
from django.db import migrations

DEFAULTS = (
    ('home_offers', '', 'popular', 9),
    ('home_side', 'جدیدترین فایل‌ها', 'latest', 6),
    ('home_discounts', 'تخفیف‌های ویژه', 'discounted', 8),
    ('home_bestsellers', 'پرفروش‌ترین‌ها', 'best_selling', 7),
)


def create_defaults(apps, schema_editor):
    ProductShowcase = apps.get_model('product', 'ProductShowcase')
    for placement, title, source, limit in DEFAULTS:
        ProductShowcase.objects.get_or_create(
            placement=placement,
            defaults={'title': title, 'source': source, 'limit': limit, 'is_active': True},
        )


class Migration(migrations.Migration):

    dependencies = [
        ('product', '0023_showcase_menu_custom_html_vendor_role'),
    ]

    operations = [
        migrations.RunPython(create_defaults, migrations.RunPython.noop),
    ]
