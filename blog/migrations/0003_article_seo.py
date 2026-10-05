from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('blog', '0002_article')]
    operations = [
        migrations.AddField(model_name='article', name='meta_title', field=models.CharField(blank=True, max_length=70, verbose_name='عنوان سئو')),
        migrations.AddField(model_name='article', name='meta_description', field=models.CharField(blank=True, max_length=160, verbose_name='توضیحات سئو')),
        migrations.AddField(model_name='article', name='canonical_url', field=models.URLField(blank=True, verbose_name='آدرس canonical')),
    ]
