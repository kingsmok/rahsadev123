# -*- coding: utf-8 -*-
"""ران نهایی جامع — روی دیتابیس تازه: همه بخش‌های سایت، سئو، ریدایرکت، پرداخت و دانلود."""
import re
import json

from django.core.management.base import BaseCommand
from django.test import Client
from django.urls import reverse, NoReverseMatch

from blog.models import Article
from cart.models import Cart, Order
from core.models import Redirect, SiteSettings
from downloads.models import DownloadToken
from pages.models import StaticPage
from payments.models import GatewaySettings, PaymentTransaction
from product.models import Product, ProductBrand, ProductCategory

PASS, FAIL = 0, 0
def ok(name, cond, detail=''):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f'  ✓ {name}' + (f' — {detail}' if detail else ''))
    else:
        FAIL += 1
        print(f'  ✗✗✗ {name} — {detail}')


class Command(BaseCommand):
    help = 'ران نهایی جامع: سلامت همه صفحات، سئو، ریدایرکت، پرداخت و دانلود — روی دیتابیس جاری'

    def handle(self, *args, **options):
        global PASS, FAIL
        PASS, FAIL = 0, 0
        anon = Client()
        demo = Client(); demo.login(username='demo', password='demo1234')
        admin = Client(); admin.login(username='admin', password='admin1234')
        roles = [('مهمان', anon), ('demo', demo), ('admin', admin)]

        print('════════ ۱) سلامت صفحات عمومی (۳ نقش) ════════')
        url_list = []
        for un in ['core:home', 'core:contact', 'core:about', 'product:product_list', 'product:discount_product',
                   'blog:article_list', 'services:services']:
            try:
                url_list.append((un, reverse(un)))
            except NoReverseMatch:
                pass
        prod = Product.objects.filter(status='published').first()
        prod2 = Product.objects.filter(status='published')[1]
        url_list += [
            ('محصول', f'/products/{prod.pid}/{prod.slug}/'),
            ('محصول۲', f'/products/{prod2.pid}/{prod2.slug}/'),
            ('دسته', f'/products/category/{ProductCategory.objects.first().slug}/'),
            ('برند', f'/products/brand/{ProductBrand.objects.first().slug}/'),
            ('مقاله', f'/blog/{Article.objects.filter(status="published").first().slug}/'),
            ('وبلاگ-دسته', '/blog/category/learn-web/'),
        ]
        for pg in StaticPage.objects.all():
            url_list.append(('صفحه ثابت', f'/pages/{pg.slug}/'))
        url_list += [('پنل ادمین', '/admin-panel/'), ('llms', '/llms.txt'), ('robots', '/robots.txt'), ('sitemap', '/sitemap.xml')]

        server_errors = []
        for name, url in url_list:
            for role, cl in roles:
                r = cl.get(url)
                if r.status_code >= 500:
                    server_errors.append((name, role, r.status_code))
        ok('بدون خطای ۵۰۰ در همه نقش‌ها', not server_errors, f'{len(url_list)}×3={len(url_list)*3} درخواست' + (f' | خطاها: {server_errors}' if server_errors else ''))

        print('════════ ۲) سئو: اسکیما + H1 + canonical + OG ════════')
        faq = StaticPage.objects.get(slug='سوالات-متداول')
        seo_pages = [
            ('خانه', '/', ['Organization', 'WebSite']),
            ('فروشگاه', '/products/', ['Organization', 'WebSite', 'BreadcrumbList', 'ItemList']),
            ('محصول', f'/products/{prod.pid}/{prod.slug}/', ['Organization', 'WebSite', 'Product', 'BreadcrumbList']),
            ('مقاله', f'/blog/{Article.objects.filter(status="published").first().slug}/', ['Organization', 'WebSite', 'BlogPosting', 'BreadcrumbList']),
            ('خدمات', '/services/', ['Organization', 'WebSite', 'Service', 'BreadcrumbList']),
            ('تماس', '/contact/', ['Organization', 'WebSite', 'ContactPage', 'BreadcrumbList']),
            ('FAQ', f'/pages/{faq.slug}/', ['Organization', 'WebSite', 'FAQPage', 'BreadcrumbList']),
        ]
        for name, url, expect in seo_pages:
            html = anon.get(url).content.decode()
            lds = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL)
            types = []
            valid = True
            for ld in lds:
                try:
                    types.append(json.loads(ld).get('@type'))
                except Exception:
                    valid = False
            has_all = all(any(t == e for t in types) for e in expect)
            h1 = html.count('<h1')
            ok(f'سئوی {name}', valid and has_all and h1 == 1 and 'canonical' in html and 'og:image' in html,
               f'schema={len(types)} h1={h1}')

        html = anon.get('/').content.decode()
        ok('og:locale و twitter:card', 'og:locale' in html and 'twitter:card' in html)
        ok('meta author = نام سایت', '<meta name="author" content="فایل‌مارکت">' in html)

        print('════════ ۳) صفحات خصوصی: noindex خودکار ════════')
        # برای صفحه پرداخت باید سبد پر باشد
        Cart.objects.filter(user__username='demo').delete()
        demo.post(f'/cart/add/{prod.id}/', data=json.dumps({'quantity': 1}), content_type='application/json')
        for name, url, cl in [('ورود', '/account/', anon), ('ثبت‌نام', '/account/register/', anon),
                              ('جست‌وجو', '/products/product_search/?q=قالب', anon),
                              ('پرداخت', '/cart/shopping_payment/', demo)]:
            html = cl.get(url).content.decode()
            m = re.search(r'<meta name="robots" content="([^"]+)"', html)
            ok(f'noindex: {name}', m is not None and 'noindex' in m.group(1), m.group(1) if m else 'بدون متا')
        Cart.objects.filter(user__username='demo').delete()

        print('════════ ۴) فایل‌های سئو ════════')
        r = anon.get('/robots.txt')
        ok('robots.txt', r.status_code == 200 and r.content.decode().count('User-agent') >= 20 and 'Sitemap:' in r.content.decode())
        sm = anon.get('/sitemap.xml')
        sm_text = sm.content.decode()
        locs = re.findall(r'<loc>(.*?)</loc>', sm_text)
        import xml.etree.ElementTree as ET
        ok('sitemap.xml', sm.status_code == 200 and len(locs) > 30 and len(locs) == len(set(locs)),
           f'{len(locs)} URL بدون تکرار')
        ok('sitemap: lastmod + تصاویر', sm_text.count('<lastmod>') > 15 and 'image:image' in sm_text)
        try:
            ET.fromstring(sm_text)
            ok('sitemap XML معتبر', True)
        except Exception as e:
            ok('sitemap XML معتبر', False, str(e))
        r = anon.get('/llms.txt')
        ok('llms.txt', r.status_code == 200 and len(r.content) > 2000, f'{len(r.content)} بایت')

        print('════════ ۵) ریدایرکت‌ها ════════')
        # نمونه‌های seed
        import urllib.parse
        for old, expected in [('/shop/', '/products/'), ('/faq/', f'/pages/{faq.slug}/'), ('/about-us/', '/about/'), ('/blog/posts/', '/blog/')]:
            r = anon.get(old)
            expected_q = urllib.parse.quote(expected)
            ok(f'ریدایرکت نمونه {old} → 301', r.status_code == 301 and r['Location'].endswith((expected, expected_q)), r.get('Location', ''))
        r = anon.get('/products/category/')
        ok('دسته خالی → فروشگاه', r.status_code in (301, 302) and r['Location'].endswith('/products/'))
        r = anon.get('/blog/category/')
        ok('دسته مقاله خالی → وبلاگ', r.status_code == 301 and r['Location'].endswith('/blog/'), r.get('Location', ''))
        r = anon.get('/shop')  # بدون اسلش
        ok('بدون اسلش انتهایی کار می‌کند', r.status_code == 301 and r['Location'].endswith('/products/'))

        # ریدایرکت خودکار تغییر نامک
        p = Product.objects.filter(status='published').first()
        orig = p.slug
        p.slug = orig + '-final'; p.save()
        r = anon.get(f'/products/{p.pid}/{orig}/')
        ok('تغییر نامک → ریدایرکت خودکار ۳۰۱', r.status_code == 301 and f'{orig}-final' in r['Location'])
        p.slug = orig; p.save()
        r = anon.get(f'/products/{p.pid}/{orig}/')
        ok('بازگشت نامک → بدون حلقه، صفحه ۲۰۰', r.status_code == 200)
        Redirect.objects.filter(old_path__contains='-final').delete()

        # شمارش hits
        Redirect.objects.update_or_create(old_path='/hit-test/', defaults={'new_path': '/products/'})
        anon.get('/hit-test/'); anon.get('/hit-test/')
        ok('شمارش دفعات استفاده', Redirect.objects.get(old_path='/hit-test/').hits >= 2)
        Redirect.objects.filter(old_path='/hit-test/').delete()

        # ادمین ریدایرکت
        r = admin.get('/admin/core/redirect/')
        ok('پنل مدیریت ریدایرکت‌ها', r.status_code == 200)

        print('════════ ۶) جریان پرداخت و دانلود ════════')
        Cart.objects.filter(user__username='demo').delete()
        demo.post(f'/cart/add/{prod.id}/', data=json.dumps({'quantity': 1}), content_type='application/json')
        html = demo.get('/cart/shopping_payment/').content.decode()
        ok('صفحه پرداخت: فقط درگاه فعال', r.status_code != 500 and 'زرین‌پال' in html and 'اسنپ‌پی' not in html)
        r = demo.post('/payments/start/new/', {'gateway': 'torobpay'}, follow=True)
        from django.contrib.messages import get_messages
        msgs = [str(m) for m in get_messages(r.wsgi_request)]
        ok('درگاه غیرفعال → پیام خطا', any('غیرفعال' in m for m in msgs) or 'غیرفعال' in r.content.decode(),
           msgs[0] if msgs else '')
        order = Order.objects.filter(user__username='demo', status='pending').first()
        ok('سفارش pending ساخته شد', order is not None)
        # شبیه‌سازی موفقیت درگاه
        tx = PaymentTransaction.objects.create(order=order, gateway='zarinpal', amount=order.final_price, authority='FINAL-TEST-1', status='pending')
        from payments.views import _complete
        _complete(tx, ref_id='REF-FINAL-1')
        order.refresh_from_db()
        ok('تکمیل پرداخت: سفارش paid + پاک شدن سبد', order.status == 'paid' and not Cart.objects.filter(user__username='demo').exists())
        tok = DownloadToken.objects.filter(order=order).first()
        ok('توکن دانلود ساخته شد', tok is not None)
        r = demo.get(f'/downloads/{tok.token}/')
        ok('دانلود فایل با توکن', r.status_code == 200)
        # پاکسازی سفارش تستی نهایی
        DownloadToken.objects.filter(order=order).delete()
        PaymentTransaction.objects.filter(order=order).delete()
        order.delete()

        print('════════ ۷) دانلودهای دمو + کوپن ════════')
        html = demo.get('/dashboard/downloads/').content.decode()
        ok('دانلودهای من: سفارش دمو', '0443419286' in html)
        Cart.objects.filter(user__username='demo').delete()
        demo.post(f'/cart/add/{prod.id}/', data=json.dumps({'quantity': 1}), content_type='application/json')
        r = demo.post('/cart/apply_coupon/', {'code': 'WELCOME10'}, follow=True)
        ok('کوپن WELCOME10 اعمال شد', 'موفق' in r.content.decode() or 'اعمال' in r.content.decode())
        Cart.objects.filter(user__username='demo').delete()

        print('════════ ۸) تنظیمات و درگاه‌ها از پنل ════════')
        gs = GatewaySettings.objects.get(key='zarinpal')
        ok('درگاه‌ها seed شده', GatewaySettings.objects.count() == 3 and gs.is_enabled)
        r = admin.get(f'/admin/payments/gatewaysettings/{gs.id}/change/')
        ok('فرم تنظیم درگاه', r.status_code == 200)
        r = admin.get(f'/admin/core/sitesettings/{SiteSettings.objects.first().id}/change/')
        ok('فرم تنظیمات سایت (سئو+تأیید)', r.status_code == 200 and 'google_site_verification' in r.content.decode())
        html = admin.get('/admin-panel/').content.decode()
        ok('پنل: وضعیت درگاه‌ها + لینک ریدایرکت', 'درگاه‌های پرداخت' in html and 'ریدایرکت' in html)

        print('════════ ۹) فرم‌ها و صفحات کاربر ════════')
        from django.contrib.auth.models import User
        User.objects.filter(username='finaltest').delete()
        r = anon.post('/account/register/', {
            'first_name': 'تست', 'last_name': 'نهایی', 'username': 'finaltest',
            'email': 'final@test.ir', 'password': 'Xk9Final77'
        }, follow=True)
        ok('ثبت‌نام کاربر جدید', User.objects.filter(username='finaltest').exists(),
           'کاربر ساخته شد' if User.objects.filter(username='finaltest').exists() else 'فرم نامعتبر: ' + str(r.context.get('form').errors if r.context and r.context.get('form') else ''))
        r = anon.post('/account/', {'username': 'finaltest', 'password': 'Xk9Final77'}, follow=True)
        ok('ورود کاربر جدید', r.request['PATH_INFO'] == '/' and r.wsgi_request.user.is_authenticated)
        User.objects.filter(username='finaltest').delete()

        r = anon.post('/contact/', {
            'first_name': 'تست', 'last_name': 'نهایی', 'phone': '09120000000',
            'subject': 'سلام', 'message': 'پیام تست نهایی'
        }, follow=True)
        ok('فرم تماس با ما', 'با موفقیت' in r.content.decode() or 'ارسال' in r.content.decode())

        print()
        print(f'════════ نتیجه نهایی: {PASS} تست موفق، {FAIL} خطا ════════')
        if FAIL:
            print('!!! خطاها باید رفع شوند !!!')
        else:
            print('همه‌چیز سبز است — ران نهایی بدون هیچ ایرادی ✓')

