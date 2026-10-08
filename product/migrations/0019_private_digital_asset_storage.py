from django.db import migrations, models

import product.storage


class Migration(migrations.Migration):

    dependencies = [
        ('product', '0018_enforce_storefront_invariants'),
    ]

    operations = [
        migrations.AlterField(
            model_name='digitalasset',
            name='file',
            field=models.FileField(
                storage=product.storage.PrivateDigitalStorage(),
                upload_to='digital-products/',
                verbose_name='فایل محصول',
            ),
        ),
    ]
