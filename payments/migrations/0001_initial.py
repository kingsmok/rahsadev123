from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = [('cart', '0007_order_items_data_alter_order_cart')]
    operations = [migrations.CreateModel(name='PaymentTransaction', fields=[
        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
        ('gateway', models.CharField(choices=[('zarinpal', 'زرین‌پال'), ('snappay', 'اسنپ‌پی'), ('torobpay', 'ترب‌پی')], max_length=20, verbose_name='درگاه')),
        ('authority', models.CharField(blank=True, max_length=120, verbose_name='شناسه درگاه')),
        ('ref_id', models.CharField(blank=True, max_length=120, verbose_name='کد رهگیری')),
        ('amount', models.PositiveBigIntegerField(verbose_name='مبلغ (تومان)')),
        ('status', models.CharField(choices=[('created', 'ایجاد شده'), ('redirected', 'ارسال به درگاه'), ('paid', 'موفق'), ('failed', 'ناموفق')], default='created', max_length=12, verbose_name='وضعیت')),
        ('raw_response', models.JSONField(blank=True, default=dict, verbose_name='پاسخ درگاه')),
        ('created_at', models.DateTimeField(auto_now_add=True)), ('updated_at', models.DateTimeField(auto_now=True)),
        ('order', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='payments', to='cart.order', verbose_name='سفارش')),
    ], options={'verbose_name':'تراکنش پرداخت','verbose_name_plural':'تراکنش‌های پرداخت','ordering':['-created_at']})]
