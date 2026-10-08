# راهنمای هاست اشتراکی / cPanel

این پروژه باید با **WSGI/Python App** هاست اجرا شود؛ `runserver` برای production نیست.
نام و مسیر Python application در cPanel بین شرکت‌ها متفاوت است، بنابراین این فایل عمداً
مسیر یا دامنه‌ی ساختگی ندارد.

## انتقال امن فایل‌های فروشی به private storage

قبل از deploy از دیتابیس و `media/` بکاپ بگیرید. سپس این ترتیب را اجرا کنید:

```bash
python manage.py migrate
python manage.py migrate_private_digital_assets
```

خروجی دوم صرفاً گزارش است. پس از بررسی تعداد فایل‌های `Would copy`:

```bash
python manage.py migrate_private_digital_assets --apply
```

فایل `digital-products.htaccess` را در این مسیر روی سرور کپی کنید:

```text
<MEDIA_ROOT>/digital-products/.htaccess
```

این rule دسترسی مستقیم `https://your-domain/media/digital-products/...` را می‌بندد؛
Django همچنان فایل را فقط پس از بررسی token دانلود می‌خواند.

پس از یک smoke test دانلود با حساب خریدار، فایل‌های عمومی قدیمی را حذف کنید:

```bash
python manage.py migrate_private_digital_assets --apply --delete-public
```

فولدر `PRIVATE_MEDIA_ROOT` باید خارج از document root باشد یا دست‌کم هیچ URL عمومی
برای آن تعریف نشود. مجوز نوشتن آن فقط باید به کاربر اجرای Python app داده شود.

## الزامات production

- `DEBUG=False`، `SECRET_KEY` تصادفی و بلند، `ALLOWED_HOSTS` و
  `CSRF_TRUSTED_ORIGINS` دقیق در `.env`.
- در cPanel SSL را فعال و HTTPS redirect را در پنل یا Apache تنظیم کنید.
- cron روزانه برای backup دیتابیس و هر دو مسیر `media/` و `private_media/`.
- اگر هاست Redis ندارد، rate limit ورود فقط در هر process اعمال می‌شود؛ WAF یا
  rate limiting ارائه‌دهنده‌ی هاست را نیز فعال کنید.
