from django.db import migrations

import django_ckeditor_5.fields


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0008_newslettersubscriber'),
    ]

    operations = [
        migrations.AlterField(
            model_name='sitesettings',
            name='text_about_us',
            field=django_ckeditor_5.fields.CKEditor5Field(
                blank=True,
                config_name='default',
                null=True,
                verbose_name='متن درباره ما',
            ),
        ),
    ]
