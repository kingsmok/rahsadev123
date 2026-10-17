"""گروه‌های نقش «فروشندگان» و «نویسندگان».

کاربرانی که همین حالا فروشندهٔ محصول یا نویسندهٔ مقاله هستند به گروه مربوط
اضافه می‌شوند تا با محدود شدن فهرست انتخاب (accounts.roles) محصولات و مقاله‌های
قبلی همچنان معتبر بمانند. هیچ داده‌ای حذف یا تغییر داده نمی‌شود.
"""
from django.db import migrations

VENDOR_GROUP = 'فروشندگان'
AUTHOR_GROUP = 'نویسندگان'


def create_role_groups(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    User = apps.get_model('auth', 'User')
    Product = apps.get_model('product', 'Product')
    Article = apps.get_model('blog', 'Article')

    vendors, _ = Group.objects.get_or_create(name=VENDOR_GROUP)
    authors, _ = Group.objects.get_or_create(name=AUTHOR_GROUP)

    vendor_ids = Product.objects.values_list('vendor_id', flat=True).distinct()
    for user in User.objects.filter(pk__in=list(vendor_ids), is_staff=False):
        user.groups.add(vendors)
    author_ids = Article.objects.values_list('author_id', flat=True).distinct()
    for user in User.objects.filter(pk__in=list(author_ids), is_staff=False):
        user.groups.add(authors)


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0004_phone_otp'),
        ('auth', '0012_alter_user_first_name_max_length'),
        ('product', '0023_showcase_menu_custom_html_vendor_role'),
        ('blog', '0008_article_custom_html_author_role'),
    ]

    operations = [
        migrations.RunPython(create_role_groups, migrations.RunPython.noop),
    ]
