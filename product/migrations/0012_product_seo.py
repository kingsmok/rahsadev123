from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('product', '0011_product_sales_count')]
    operations = [
        migrations.AddField(model_name='product', name='meta_title', field=models.CharField(blank=True, max_length=70, verbose_name='عنوان سئو')),
        migrations.AddField(model_name='product', name='meta_description', field=models.CharField(blank=True, max_length=160, verbose_name='توضیحات سئو')),
        migrations.AddField(model_name='product', name='canonical_url', field=models.URLField(blank=True, verbose_name='آدرس canonical')),
    ]
