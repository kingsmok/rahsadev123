from django.db import migrations

import django_ckeditor_5.fields


class Migration(migrations.Migration):

    dependencies = [
        ('pages', '0002_alter_staticpage_options'),
    ]

    operations = [
        migrations.AlterField(
            model_name='staticpage',
            name='content',
            field=django_ckeditor_5.fields.CKEditor5Field(config_name='default', verbose_name='محتوا'),
        ),
    ]
