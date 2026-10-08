from django.db import migrations

import django_ckeditor_5.fields


class Migration(migrations.Migration):

    dependencies = [
        ('blog', '0005_alter_article_options_alter_category_options'),
    ]

    operations = [
        migrations.AlterField(
            model_name='article',
            name='description',
            field=django_ckeditor_5.fields.CKEditor5Field(config_name='default', verbose_name='متن مقاله'),
        ),
    ]
