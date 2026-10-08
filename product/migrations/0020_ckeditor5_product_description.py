from django.db import migrations

import django_ckeditor_5.fields


class Migration(migrations.Migration):

    dependencies = [
        ('product', '0019_private_digital_asset_storage'),
    ]

    operations = [
        migrations.AlterField(
            model_name='product',
            name='description',
            field=django_ckeditor_5.fields.CKEditor5Field(config_name='default', verbose_name='توضیحات تکمیلی'),
        ),
    ]
