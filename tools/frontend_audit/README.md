# ابزار ممیزی فرانت‌اند با مرورگر واقعی

این اسکریپت‌ها برای ممیزیِ اندازه‌گیری‌شدهٔ فرانت‌اند (سرریز افقی، اهداف لمسی،
هم‌پوشانی و تعامل‌های موبایل) با Chromium واقعی headless استفاده شده‌اند.

## چرا Chromium از npm؟

در محیط CI/سندباکس این پروژه، CDNهای Playwright و apt در دسترس نبودند.
بستهٔ `@sparticuz/chromium` باینری Chromium را **داخل خود tarball npm** دارد
و از `registry.npmjs.org` نصب می‌شود. کتابخانه‌های NSS لازم
(`libnss3`, `libnspr4`, `libnssutil3`) هم داخل همان بسته، در
`bin/al2023.tar.br` موجود است.

## راه‌اندازی

```bash
mkdir -p /tmp/browser && cd /tmp/browser
npm install @sparticuz/chromium puppeteer-core
node -e "
const fs=require('fs'), zlib=require('zlib');
fs.writeFileSync('chromium', zlib.brotliDecompressSync(
  fs.readFileSync('node_modules/@sparticuz/chromium/bin/chromium.br')), {mode:0o755});
fs.writeFileSync('al2023.tar', zlib.brotliDecompressSync(
  fs.readFileSync('node_modules/@sparticuz/chromium/bin/al2023.tar.br')));
"
mkdir -p al2023 && tar -xf al2023.tar -C al2023
# سرور جنگو باید روی 127.0.0.1:8000 در حال اجرا باشد
```

## اسکریپت‌ها

| فایل | کار |
|---|---|
| `sweep.js` | پویش کامل: ۱۰ صفحه × ۱۳ عرض (۳۲۰ تا ۱۴۴۰) × ۲ نقش؛ سرریز افقی، عناصر بیرون‌زدهٔ روی صفحه، اهداف لمسی زیر ۴۴px و هم‌پوشانی‌ها را در `sweep.json` ذخیره می‌کند |
| `interact.js` | تست تعامل موبایل: باز/بسته‌شدن منوی همبرگری با لمس و Escape، تغییر اندازه با منوی باز، حالت افقی |
| `verify-fixes.js` | راستی‌آزمایی اصلاحات مشخص (فرم خبرنامه در ۳۲۰px، ناحیهٔ لمس دکمهٔ سبد) |
| `ext.js` | پویش توسعه‌یافتهٔ دور ششم: ۱۸ صفحه × ۵ عرض (تا ۱۹۲۰) + پنل مدیریت، خطاهای کنسول/شبکه، اندازهٔ لیبل فیلترها |
| `interact2.js` | تعامل‌های دور ششم: کشوی سبد با لمس و Escape، خطای ورود اشتباه، منوی داشبورد موبایل، اسکرین‌شات ۳۲۰px جزئیات محصول و سبد |
| `perf.js` | وزن صفحه در موبایل: مجموع بایت انتقالی، بزرگ‌ترین منابع، پوشش lazy تصاویر |
| `coarse.js` | شبیه‌سازی دستگاه لمسی واقعی (iPhone 12): راستی‌آزمایی اهداف لمسی در `(pointer: coarse)` |
| `runserver_mock.py` | سرور توسعه برای تستِ پرداخت در سندباکس: **فقط** فراخوانی بیرونیِ API زرین‌پال با پاسخی هم‌شکلِ واقعی جایگزین می‌شود؛ بقیهٔ مسیر (ویو، CSP، قالب) کدِ واقعی است |
| `checkout_csp.js` | جریان کامل پرداخت با مرورگر واقعی: ورود ← افزودن به سبد ← ارسال فرم پرداخت؛ باید مرورگر به صفحهٔ درگاه برود و هیچ نقض CSP (`form-action`) ثبت نشود |
| `sweep_console.js` | پویش نقش‌ها × موبایل/دسکتاپ: خطای JS، نقض CSP، درخواست ناموفق یا ۴xx/۵xx، سرریز افقی و بریدگیِ بیرون از ظرف اسکرول؛ ورودی فهرست صفحات (`pages.json`) |

اجرا:

```bash
cd /tmp/browser   # جایی که chromium و node_modules هستند
cp /path/to/repo/tools/frontend_audit/*.js .
node sweep.js
node interact.js
```

نکته: عناصر off-canvas (کشوی ناوبری، کشوی سبد، اسلایدهای پارک‌شدهٔ کاروسل)
عمداً از محاسبهٔ سرریز حذف شده‌اند؛ فقط عناصرِ حداقل تا حدی روی صفحه شمرده می‌شوند.

برای `checkout_csp.js` سرور را با `runserver_mock.py` اجرا کنید (روی دیتابیس دمو؛ تنظیمات زرین‌پال در همان دیتابیس فعال و سندباکس می‌شود):

```bash
DEBUG=True SECRET_KEY=... .venv/bin/python tools/frontend_audit/runserver_mock.py 127.0.0.1:8000
cd /tmp/browser && node checkout_csp.js
```
