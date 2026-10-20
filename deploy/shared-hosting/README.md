# راهنمای هاست اشتراکی / cPanel

این پروژه باید با **WSGI/Python App** هاست اجرا شود؛ `runserver` برای production نیست.
نام و مسیر Python application در cPanel بین شرکت‌ها متفاوت است، بنابراین مسیر و دامنه را
با اطلاعات واقعی سرویس خود جایگزین کنید.

## تنظیم پیشنهادی برای ۱ هسته CPU و ۱ گیگابایت RAM

1. در cPanel یک **Python App** با Python 3.10 یا جدیدتر بسازید؛ Application root را
   ریشهٔ همین پروژه، Startup file را `passenger_wsgi.py` و Entry point را
   `application` قرار دهید.
2. تعداد process/worker را **۱** نگه دارید. اجرای هم‌زمان `runserver`، Celery یا worker
   دوم روی این پلن لازم نیست و اتصال SQL و RAM را هدر می‌دهد.
3. اگر SSH ندارید، در بخش **Environment Variables** برنامهٔ Python یک کلید با نام
   `INSTALLER_TOKEN` و یک مقدار تصادفی و طولانی (حداقل ۳۲ کاراکتر) بسازید. برنامه را
   Restart و دامنه را باز کنید. فرم نصب در مرورگر نمایش داده می‌شود و موارد زیر را
   خودکار انجام می‌دهد:

   - نصب requirements در همان محیط Python؛
   - ساخت `.env` با دسترسی فقط برای صاحب فایل؛
   - تست واقعی اتصال SQL و اجرای migrationها؛
   - اجرای collectstatic؛
   - ساخت یا بازنشانی رمز حساب superuser.

   بعد از پیام موفقیت، `INSTALLER_TOKEN` را از پنل حذف و Python App را Restart کنید.
   بدون کلید صحیح هیچ‌کس نمی‌تواند نصب را آغاز کند. اگر نصب وسط کار قطع شود، فایل
   `.installing` باعث می‌شود فرم نصب در دسترس بماند و سایت نیمه‌نصب‌شده اجرا نشود.

   اگر هاست اجازهٔ اجرای pip از درخواست وب را ندهد، در بخش Setup Python App پنل از
   قابلیت **Run Pip Install / Configuration files** استفاده کرده و `requirements.txt`
   را انتخاب کنید، سپس فرم را دوباره ارسال کنید.

   روش جایگزین برای هاست دارای ترمینال همچنان این است:

```bash
python install_shared_hosting.py
```

4. دامنهٔ `/static/` را در پنل به پوشهٔ `staticfiles/` و `/media/` را به `media/`
   نگاشت کنید. سپس از Python App گزینهٔ Restart را بزنید (در Passenger معمولاً
   `mkdir -p tmp && touch tmp/restart.txt` نیز برنامه را ری‌استارت می‌کند).
5. برای کارهای دوره‌ای فقط cronهای کوتاه اجرا کنید؛ از daemon دائمی استفاده نکنید.

### اتصال MySQL/MariaDB هاست

ابتدا در cPanel پایگاه و کاربر بسازید و کاربر را با **ALL PRIVILEGES** به پایگاه متصل
کنید. سپس در `.env` بنویسید:

```dotenv
DATABASE_URL=mysql://cpanel_user:URL_ENCODED_PASSWORD@localhost:3306/cpanel_database
DB_CONN_MAX_AGE=0
```

نام کاربر و دیتابیس در cPanel معمولاً پیشوند حساب دارند. اگر رمز شامل `@`، `#`، `/`
یا `:` است باید URL-encode شود (`@` برابر `%40` و `#` برابر `%23`). مقدار Host و Port
را دقیقاً از شرکت میزبان بگیرید؛ همیشه `localhost` نیست. درایور pure-Python پروژه به
کامپایلر سیستمی نیاز ندارد و با MySQL/MariaDB کار می‌کند. `utf8mb4` و strict mode نیز
خودکار فعال می‌شوند تا متن فارسی و اطلاعات سفارش ناقص ذخیره نشود.

برای PostgreSQL به‌جای آن بنویسید:

```dotenv
DATABASE_URL=postgresql://user:URL_ENCODED_PASSWORD@host:5432/database
DB_CONN_MAX_AGE=0
```

برای تست اتصال، قبل از Restart اجرا کنید:

```bash
python manage.py check --database default
python manage.py migrate --noinput
```

`DB_CONN_MAX_AGE=0` برای سقف پایین اتصال SQL امن‌تر است. فقط اگر میزبان اجازهٔ اتصال
ماندگار داده آن را مثلاً `60` کنید. کش پیش‌فرض پروژه در همان process است و به Redis
نیاز ندارد. فایل نمونه همچنین سقف حافظهٔ upload را پایین نگه می‌دارد؛ برای فایل محصول
حجیم از گزینهٔ «لینک دانلود» و هاست دانلود استفاده کنید.

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
- اگر اپلیکیشن پشت یک reverse proxy اجرا می‌شود که TLS را همان‌جا قطع می‌کند،
  حتماً `BEHIND_HTTPS_PROXY=1` را هم تنظیم کنید. در غیر این صورت
  `SECURE_SSL_REDIRECT` همیشه درخواست را HTTP می‌بیند و سایت وارد **حلقهٔ
  بی‌پایان ریدایرکت** می‌شود. این گزینه را روی اتصالی که پروکسیِ مطمئن ندارد
  فعال نکنید (امکان جعل هدر و دورزدن HTTPS).
- در cPanel SSL را فعال و HTTPS redirect را در پنل یا Apache تنظیم کنید.
- cron روزانه برای backup دیتابیس و هر دو مسیر `media/` و `private_media/`.
- اگر هاست Redis ندارد، rate limit ورود و فرم‌ها فقط در هر process اعمال می‌شود؛
  WAF یا rate limiting ارائه‌دهنده‌ی هاست را نیز فعال کنید.

## لاگ‌ها و خطایابی

پروژه یک پیکربندی لاگ آماده دارد: رکوردهای `django.request` و لاگرهای
`payments` / `cart` / `downloads` همیشه روی stderr نوشته می‌شوند (gunicorn،
systemd یا «Python App» ی cPanel آن‌ها را جمع‌آوری می‌کند). این تنظیم عمداً
اضافه شده چون پیکربندی پیش‌فرض جنگو خطاهای ۵۰۰ را فقط به `mail_admins`
می‌فرستد و در صورت خالی‌بودن `ADMINS` آن‌ها را کاملاً نادیده می‌گیرد — یعنی یک
کال‌بک پرداختِ ناموفق هیچ اثری باقی نمی‌گذاشت.

برای نگه‌داری در فایل، در `.env` مقدار `LOG_FILE` را تنظیم کنید (همراه
`LOG_FILE_MAX_BYTES` و `LOG_FILE_BACKUP_COUNT` برای چرخش خودکار).

اگر تراکنشی در پنل با `raw_response.unfulfilled: true` دیده شد، یعنی درگاه
پرداخت را تأیید کرده اما تحویل خودکار سفارش انجام نشده است (مثلاً فایل حذف
شده بود). مبلغ از مشتری گرفته شده و باید از آن تراکنش پیگیری یا مسترد شود.
