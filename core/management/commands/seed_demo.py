"""
پرکردن فروشگاه با داده‌های نمونه:
    python manage.py seed_demo

- کاربر مدیر: admin / admin1234
- کاربر نمونه: demo / demo1234
- دسته‌بندی‌ها، برندها، ۱۴ محصول دیجیتال (همراه با فایل قابل دانلود)، بنرها،
  پکیج‌های طراحی سایت، نمونه کارها، مقالات، صفحات ثابت و کد تخفیف
"""
import os
import zipfile
from io import BytesIO

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.core.files.images import ImageFile
from django.core.management.base import BaseCommand
from django.utils import timezone

from blog.models import Article, Category as ArticleCategory, Tag
from cart.models import Coupon, Order, OrderItem
from core.models import Banner, SiteSettings
from pages.models import StaticPage
from product.models import DigitalAsset, Product, ProductBrand, ProductCategory, ProductComment
from services.models import PortfolioItem, ServicePackage
from payments.models import GatewaySettings

SEED_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', 'media', 'seed')
PRODUCT_IMAGES = os.path.join(SEED_DIR, 'products')
BANNER_IMAGES = os.path.join(SEED_DIR, 'banners')
PORTFOLIO_IMAGES = os.path.join(SEED_DIR, 'portfolio')


def make_zip(product_title, files):
    """ساخت فایل زیپ واقعی برای دانلود محصول."""
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('README.txt', (
            f'{product_title}\n'
            '================================\n\n'
            'با تشکر از خرید شما از فایل‌مارکت!\n\n'
            'این بسته شامل فایل‌های محصول، مستندات نصب و راه‌اندازی و اطلاعات لایسنس است.\n'
            'در صورت هرگونه مشکل با پشتیبانی در تماس باشید.\n'
        ).encode('utf-8'))
        for filename, content in files.items():
            zf.writestr(filename, content.encode('utf-8'))
    buffer.seek(0)
    return ContentFile(buffer.read())


class Command(BaseCommand):
    help = 'پرکردن فروشگاه با داده‌های نمونه (دسته‌ها، فایل‌ها، بنرها، خدمات و ...)'

    def handle(self, *args, **options):
        self.stdout.write('شروع ثبت داده‌های نمونه...')

        # ------------------------------------------------------------------ کاربران
        admin, created = User.objects.get_or_create(
            username='admin',
            defaults={'is_staff': True, 'is_superuser': True, 'email': 'admin@filemarket.ir'},
        )
        if created:
            admin.set_password('admin1234')
            admin.save()
            self.stdout.write(self.style.SUCCESS('کاربر مدیر ساخته شد: admin / admin1234'))

        demo, created = User.objects.get_or_create(
            username='demo',
            defaults={'email': 'demo@filemarket.ir', 'first_name': 'کاربر', 'last_name': 'نمونه'},
        )
        if created:
            demo.set_password('demo1234')
            demo.save()
            self.stdout.write(self.style.SUCCESS('کاربر نمونه ساخته شد: demo / demo1234'))

        # ------------------------------------------------------------------ تنظیمات سایت
        if not SiteSettings.objects.exists():
            SiteSettings.objects.create(
                site_name='فایل‌مارکت',
                site_slogan='مارکت فایل، نرم‌افزار و محصولات مجازی',
                text_about_us=(
                    '<p><b>فایل‌مارکت</b> مرجع تخصصی خرید و دانلود <b>فایل‌های نرم‌افزاری</b>، '
                    '<b>قالب و افزونه وب سایت</b>، <b>اسکریپت‌های آماده</b>، <b>فایل‌های طراحی</b> و '
                    '<b>محصولات مجازی</b> است.</p>'
                    '<p>ما با هدف ساماندهی بازار محصولات دیجیتال ایران راه‌اندازی شده‌ایم؛ همه فایل‌های این '
                    'مجموعه دارای لایسنس رسمی، پشتیبانی فنی و به‌روزرسانی منظم هستند و بلافاصله پس از پرداخت '
                    'قابل دانلود خواهند بود. علاوه بر فروش فایل آماده، تیم طراحی ما آماده ساخت وب سایت اختصاصی '
                    'شماست؛ از سایت شرکتی و فروشگاهی گرفته تا پرتال‌های سازمانی.</p>'
                    '<p>پشتیبانی مسئولانه، تحویل آنی و شفافیت کامل در قیمت‌گذاری، سه اصل همیشگی ماست.</p>'
                ),
                text_contact_us=(
                    'برای هرگونه سؤال، پیشنهاد یا مشکل در خرید و دانلود فایل‌ها می‌توانید از این فرم استفاده کنید. '
                    'کارشناسان ما در سریع‌ترین زمان ممکن پاسخ می‌دهند.'
                ),
                address='تهران، خیابان ولیعصر، بالاتر از پارک ساعی، پلاک ۲۱۸۰، واحد ۹',
                phone1='02191008080',
                phone2='02143057070',
                email1='support@filemarket.ir',
                email2='info@filemarket.ir',
                footer_description=(
                    'فایل‌مارکت مرجع تخصصی خرید و دانلود فایل‌های نرم‌افزاری، قالب و افزونه وب سایت، اسکریپت، '
                    'فایل‌های طراحی و محصولات مجازی است. همه فایل‌ها با لایسنس رسمی و پشتیبانی فنی ارائه می‌شوند '
                    'و بلافاصله پس از پرداخت قابل دانلود هستند.'
                ),
                copy_right='تمامی حقوق مادی و معنوی این سایت برای فایل‌مارکت محفوظ است.',
                instagram_link='https://instagram.com/filemarket',
                telegram_link='https://t.me/filemarket',
                enamad_link='https://trustseal.enamad.ir',
                samandehi_link='https://markazsazmani.ir',
                default_meta_title='فایل‌مارکت | مارکت فایل و محصولات مجازی',
                default_meta_description=(
                    'خرید و دانلود آنی فایل‌های نرم‌افزاری، قالب وب سایت، افزونه، اسکریپت، فایل‌های طراحی و '
                    'محصولات مجازی همراه با لایسنس رسمی، به‌روزرسانی و پشتیبانی فنی.'
                ),
            )
            self.stdout.write('تنظیمات سایت ثبت شد.')

        # ------------------------------------------------------------------ دسته‌بندی‌ها
        categories_data = [
            ('قالب وردپرس', 'wordpress-themes', 'fa-wordpress'),
            ('قالب HTML و سایت آماده', 'html-templates', 'fa-file-code'),
            ('افزونه وردپرس', 'wordpress-plugins', 'fa-plug'),
            ('اسکریپت و کد آماده', 'php-scripts', 'fa-code'),
            ('نرم‌افزار و ابزار', 'software-tools', 'fa-desktop'),
            ('فایل‌های طراحی', 'design-files', 'fa-palette'),
            ('محصولات مجازی', 'virtual-products', 'fa-gift'),
        ]
        categories = {}
        for title, slug, icon in categories_data:
            obj, _ = ProductCategory.objects.get_or_create(slug=slug, defaults={'title': title, 'icon': icon})
            categories[title] = obj

        # ------------------------------------------------------------------ برندها / سازنده‌ها
        brands_data = [
            ('استودیو راها', 'raha-studio'),
            ('انواتو', 'envato'),
            ('کدی‌کنیون', 'codecanyon'),
            ('نرم‌افزاری آریا', 'aria-soft'),
            ('کریتیو مارکت', 'creative-market'),
        ]
        brands = {}
        for title, slug in brands_data:
            obj, _ = ProductBrand.objects.get_or_create(slug=slug, defaults={'title': title})
            brands[title] = obj

        # ------------------------------------------------------------------ محصولات
        products_data = [
            {
                'title': 'قالب وردپرس فروشگاهی شاپینو',
                'slug': 'shopino-woocommerce-theme',
                'category': 'قالب وردپرس',
                'brand': 'استودیو راها',
                'product_type': 'template',
                'license_type': 'single',
                'price': 2900000, 'old_price': 3500000,
                'image': 'wp-shop-theme.png',
                'short_description': 'قالب فروشگاهی حرفه‌ای وردپرس با پشتیبانی کامل از ووکامرس و درگاه‌های ایرانی',
                'description': (
                    '<p><b>شاپینو</b> یک قالب وردپرس فروشگاهی کاملاً فارسی و راست‌چین است که با بهره‌گیری از '
                    'ووکامرس، راه‌اندازی فروشگاه اینترنتی شما را در کمترین زمان ممکن می‌کند.</p>'
                    '<h3>ویژگی‌های کلیدی</h3>'
                    '<ul><li>طراحی ریسپانسیو و سازگار با موبایل و تبلت</li>'
                    '<li>پشتیبانی از درگاه‌های پرداخت ایرانی (زرین‌پال، ...) و اتصال به پست ایران</li>'
                    '<li>۷ صفحه اصلی متفاوت + بیش از ۲۰ المان صفحه‌ساز</li>'
                    '<li>سرعت بارگذاری بالا و بهینه برای سئو</li></ul>'
                    '<p>پس از خرید، فایل قالب به همراه مستندات نصب گام‌به‌گام تحویل داده می‌شود.</p>'
                ),
                'file_type': 'ZIP', 'version': '3.2.1', 'file_prefix': 'shopino',
                'requirements': 'وردپرس 6.0+\nووکامرس 7.0+\nPHP 8.0+',
                'support_duration': '۶ ماه',
                'update_duration': '۱۲ ماه',
                'demo_url': 'https://demo.filemarket.ir/shopino',
                'documentation_url': 'https://docs.filemarket.ir/shopino',
                'changelog': 'نسخه ۳.۲.۱:\n- افزودن ۲ صفحه اصلی جدید\n- بهبود سرعت صفحه محصول\n- رفع مشکل سازگاری با ووکامرس جدید',
                'featured': True, 'sales': 412, 'views': 5230,
            },
            {
                'title': 'قالب وردپرس شرکتی کورپوریت‌پرو',
                'slug': 'corporate-pro-wordpress-theme',
                'category': 'قالب وردپرس',
                'brand': 'استودیو راها',
                'product_type': 'template',
                'license_type': 'single',
                'price': 1850000, 'old_price': None,
                'image': 'wp-corp-theme.png',
                'short_description': 'قالب شرکتی مدرن و کلاس برای سایت‌های شرکت‌ها، هلدینگ‌ها و استارتاپ‌ها',
                'description': (
                    '<p><b>کورپوریت‌پرو</b> برای سایت‌های شرکتی طراحی شده است؛ با صفحه اصلی متحرک، بخش معرفی '
                    'خدمات، نمونه کارها، تیم و اخبار شرکت.</p>'
                    '<ul><li>پنل تنظیمات اختصاصی و آسان</li>'
                    '<li>سازگار با المنتور و گوتنبرگ</li>'
                    '<li>چند زبانه (WPML) و سئو شده</li></ul>'
                ),
                'file_type': 'ZIP', 'version': '2.4.0', 'file_prefix': 'corporate-pro',
                'requirements': 'وردپرس 6.0+\nPHP 7.4+',
                'support_duration': '۶ ماه',
                'update_duration': '۱۲ ماه',
                'demo_url': 'https://demo.filemarket.ir/corporate-pro',
                'sales': 268, 'views': 3410,
            },
            {
                'title': 'قالب HTML ریسپانسیو لندینگ پلاس',
                'slug': 'landing-plus-html-template',
                'category': 'قالب HTML و سایت آماده',
                'brand': 'کریتیو مارکت',
                'product_type': 'template',
                'license_type': 'multi',
                'price': 890000, 'old_price': 1200000,
                'image': 'html-landing.png',
                'short_description': 'قالب لندینگ HTML5/CSS3 با ۱۲ دموی آماده برای محصولات و اپلیکیشن‌ها',
                'description': (
                    '<p><b>لندینگ پلاس</b> بسته‌ای از ۱۲ صفحه فرود آماده است که برای معرفی محصول، اپلیکیشن، '
                    'دوره آموزشی و کمپین‌های تبلیغاتی طراحی شده‌اند.</p>'
                    '<ul><li>کدنویسی تمیز بر اساس Bootstrap 5</li>'
                    '<li>انیمیشن‌های Scroll و افکت‌های آماده</li>'
                    '<li>فرم تماس کاربردی و آماده اتصال به میل‌سرور</li></ul>'
                ),
                'file_type': 'ZIP', 'version': '5.1.0', 'file_prefix': 'landing-plus',
                'requirements': 'مرورگر مدرن\nسرور هاست (برای انتشار)',
                'support_duration': '۳ ماه',
                'update_duration': '۶ ماه',
                'demo_url': 'https://demo.filemarket.ir/landing-plus',
                'sales': 517, 'views': 6120, 'featured': True,
            },
            {
                'title': 'افزونه درگاه پرداخت امن پی‌لینک',
                'slug': 'paylink-secure-payment-plugin',
                'category': 'افزونه وردپرس',
                'brand': 'نرم‌افزاری آریا',
                'product_type': 'plugin',
                'license_type': 'single',
                'price': 1250000, 'old_price': None,
                'image': 'plugin-payment.png',
                'short_description': 'اتصال فروشگاه وردپرسی شما به تمام درگاه‌های پرداخت معتبر ایرانی در یک افزونه',
                'description': (
                    '<p>با <b>پی‌لینک</b> در یک افزونه به همه درگاه‌های پرداخت ایرانی متصل شوید؛ زرین‌پال، '
                    'سامان، پارسیان، ملت و ... .</p>'
                    '<ul><li>پرداخت خودکار و دستی و گزارش تراکنش‌ها</li>'
                    '<li>امنیت بالا با تأیید دو مرحله‌ای SHA-256</li>'
                    '<li>بازگشت خودکار مشتری و ثبت خودکار سفارش</li></ul>'
                ),
                'file_type': 'ZIP', 'version': '4.0.2', 'file_prefix': 'paylink',
                'requirements': 'وردپرس 5.8+\nووکامرس 6.0+',
                'support_duration': '۱۲ ماه',
                'update_duration': '۱۲ ماه',
                'documentation_url': 'https://docs.filemarket.ir/paylink',
                'sales': 730, 'views': 8015,
            },
            {
                'title': 'افزونه سئو و بهینه‌سازی سئوپرو',
                'slug': 'seopro-wordpress-plugin',
                'category': 'افزونه وردپرس',
                'brand': 'نرم‌افزاری آریا',
                'product_type': 'plugin',
                'license_type': 'subscription',
                'price': 690000, 'old_price': 990000,
                'image': 'plugin-seo.png',
                'short_description': 'ابزار کامل سئو داخلی وردپرس؛ اسکیمای فارسی، نقشه سایت و تحلیل محتوا',
                'description': (
                    '<p><b>سئوپرو</b> جایگزین کامل افزونه‌های سنگین سئو است؛ با پشتیبانی کامل از زبان فارسی و '
                    'اسکیماهای مناسب موتورهای جستجوی فارسی‌زبان.</p>'
                    '<ul><li>ساخت خودکار Schema فارسی</li>'
                    '<li>نقشه سایت و روبات‌های هوشمند</li>'
                    '<li>تحلیل زنده محتوا هنگام نگارش</li></ul>'
                ),
                'file_type': 'ZIP', 'version': '2.8.0', 'file_prefix': 'seopro',
                'requirements': 'وردپرس 5.5+\nPHP 7.4+',
                'support_duration': '۱۲ ماه',
                'update_duration': '۱۲ ماه',
                'sales': 389, 'views': 4455,
            },
            {
                'title': 'اسکریپت فروش فایل و محصولات مجازی فایل‌سل',
                'slug': 'filesell-php-script',
                'category': 'اسکریپت و کد آماده',
                'brand': 'نرم‌افزاری آریا',
                'product_type': 'script',
                'license_type': 'lifetime',
                'price': 4500000, 'old_price': 5400000,
                'image': 'script-filesell.png',
                'short_description': 'اسکریپت کامل فروش فایل با درگاه پرداخت، مدیریت دانلود و پنل کاربری',
                'description': (
                    '<p><b>فایل‌سل</b> یک اسکریپت PHP کامل برای راه‌اندازی فروشگاه فروش فایل و محصولات مجازی است؛ '
                    'همان سیستمی که همین فروشگاه با آن کار می‌کند!</p>'
                    '<ul><li>پنل مدیریت کامل با گزارش فروش و تراکنش‌ها</li>'
                    '<li>لینک دانلود امن با محدودیت تعداد و تاریخ انقضا</li>'
                    '<li>درگاه زرین‌پال + ساخت خودکار فاکتور</li>'
                    '<li>سیستم کد تخفیف و اشتراک ویژه</li></ul>'
                ),
                'file_type': 'ZIP', 'version': '1.9.3', 'file_prefix': 'filesell',
                'requirements': 'PHP 8.1+\nMySQL 5.7+\nComposer',
                'support_duration': '۱۲ ماه',
                'update_duration': 'نامحدود',
                'documentation_url': 'https://docs.filemarket.ir/filesell',
                'changelog': 'نسخه ۱.۹.۳:\n- افزودن گزارش‌گیری اکسل از سفارش‌ها\n- بهبود امنیت لینک‌های دانلود',
                'sales': 156, 'views': 7320, 'featured': True,
            },
            {
                'title': 'اسکریپت رزرو نوبت آنلاین نوبت‌یار',
                'slug': 'nobatyar-booking-script',
                'category': 'اسکریپت و کد آماده',
                'brand': 'نرم‌افزاری آریا',
                'product_type': 'script',
                'license_type': 'lifetime',
                'price': 3200000, 'old_price': None,
                'image': 'script-booking.png',
                'short_description': 'سیستم رزرو نوبت آنلاین برای مطب‌ها، کلینیک‌ها و مراکز خدماتی',
                'description': (
                    '<p><b>نوبت‌یار</b> به پزشکان، آرایشگاه‌ها و مراکز خدماتی اجازه می‌دهد نوبت‌مندی خود را '
                    'کاملاً آنلاین مدیریت کنند.</p>'
                    '<ul><li>تقویم کاری و مدیریت شیفت‌ها</li>'
                    '<li>اطلاع‌رسانی پیامکی (اتصال به پنل پیامک)</li>'
                    '<li>پنل جداگانه برای منشی و متخصص</li></ul>'
                ),
                'file_type': 'ZIP', 'version': '2.1.0', 'file_prefix': 'nobatyar',
                'requirements': 'PHP 8.0+\nMySQL 5.7+',
                'support_duration': '۱۲ ماه',
                'update_duration': '۱۲ ماه',
                'sales': 98, 'views': 2870,
            },
            {
                'title': 'نرم‌افزار حسابداری حسابیار پرو',
                'slug': 'hesabyar-pro-accounting',
                'category': 'نرم‌افزار و ابزار',
                'brand': 'نرم‌افزاری آریا',
                'product_type': 'software',
                'license_type': 'single',
                'price': 5900000, 'old_price': 6800000,
                'image': 'software-accounting.png',
                'short_description': 'نرم‌افزار حسابداری کامل برای کسب‌وکارهای کوچک و متوسط با صدور فاکتور رسمی',
                'description': (
                    '<p><b>حسابیار پرو</b> با محیط ساده و فارسی، حسابداری کسب‌وکار شما را ساده می‌کند.</p>'
                    '<ul><li>صدور فاکتور فروش و خرید + پرینت رسمی</li>'
                    '<li>انبارداری، چک، تنخواه و گزارش‌های مالی</li>'
                    '<li>پشتیبان‌گیری خودکار و رمزگذاری اطلاعات</li></ul>'
                    '<p>نسخه ویندوز؛ لایسنس دائمی روی یک سیستم.</p>'
                ),
                'file_type': 'ZIP', 'version': '8.4.1', 'file_prefix': 'hesabyar',
                'requirements': 'ویندوز 10/11\nحداقل ۴ گیگابایت رم',
                'operating_system': 'ویندوز 10، ویندوز 11',
                'support_duration': '۱۲ ماه',
                'update_duration': '۱۲ ماه',
                'sales': 265, 'views': 5125,
            },
            {
                'title': 'نرم‌افزار مدیریت پروژه و وظایف تسک‌بان',
                'slug': 'taskban-project-management',
                'category': 'نرم‌افزار و ابزار',
                'brand': 'استودیو راها',
                'product_type': 'software',
                'license_type': 'multi',
                'price': 2400000, 'old_price': None,
                'image': 'software-tasks.png',
                'short_description': 'ابزار مدیریت پروژه تیمی با برد کانبان، تقویم و گزارش پیشرفت',
                'description': (
                    '<p><b>تسک‌بان</b> نرم‌افزار دسکتاپ مدیریت وظایف برای تیم‌های کوچک است.</p>'
                    '<ul><li>برد کانبان و نمای تقویمی</li>'
                    '<li>همگام‌سازی ابری بین اعضای تیم</li>'
                    '<li>گزارش پیشرفت و نمودارهای تحلیلی</li></ul>'
                ),
                'file_type': 'ZIP', 'version': '3.0.0', 'file_prefix': 'taskban',
                'requirements': 'ویندوز 10/11 یا macOS 12+',
                'operating_system': 'ویندوز، مک',
                'support_duration': '۶ ماه',
                'update_duration': '۱۲ ماه',
                'sales': 143, 'views': 3120,
            },
            {
                'title': 'پکیج UI Kit داشبورد مدیریت نکسا',
                'slug': 'nexa-admin-dashboard-uikit',
                'category': 'فایل‌های طراحی',
                'brand': 'کریتیو مارکت',
                'product_type': 'design_file',
                'license_type': 'multi',
                'price': 780000, 'old_price': 950000,
                'image': 'design-uikit.png',
                'short_description': 'کیت رابط کاربری کامل داشبورد ادمین شامل ۱۲۰+ کامپوننت در فرمت Figma',
                'description': (
                    '<p><b>نکسا</b> یک UI Kit کامل برای طراحی داشبوردهای مدیریتی است؛ شامل ۱۲۰+ کامپوننت '
                    'آماده، ۴۰ صفحه نمونه و سیستم طراحی منظم.</p>'
                    '<ul><li>فرمت Figma با کامپوننت‌های واریانت‌دار</li>'
                    '<li>حالت روشن و تاریک</li>'
                    '<li>راست‌چین و بهینه برای پروژه‌های فارسی</li></ul>'
                ),
                'file_type': 'ZIP', 'version': '1.5.0', 'file_prefix': 'nexa-uikit',
                'requirements': 'Figma (حساب رایگان کافی است)',
                'support_duration': '۳ ماه',
                'update_duration': '۶ ماه',
                'sales': 324, 'views': 4680,
            },
            {
                'title': 'پکیج موکاپ برندینگ حرفه‌ای لایه‌باز',
                'slug': 'branding-mockup-pack',
                'category': 'فایل‌های طراحی',
                'brand': 'کریتیو مارکت',
                'product_type': 'design_file',
                'license_type': 'single',
                'price': 350000, 'old_price': 550000,
                'image': 'design-mockup.png',
                'short_description': '۳۰ موکاپ لایه‌باز PSD برای ارائه هویت بصری برند؛ کارت ویزیت، ست اداری و ...',
                'description': (
                    '<p>بسته <b>موکاپ برندینگ</b> شامل ۳۰ فایل PSD لایه‌باز و باکیفیت برای ارائه حرفه‌ای '
                    'طرح‌های هویت بصری است.</p>'
                    '<ul><li>سمارت‌آبجکت؛ جایگذاری طرح با یک کلیک</li>'
                    '<li>رزولوشن ۴K</li>'
                    '<li>نورپردازی و سایه‌های واقعی</li></ul>'
                ),
                'file_type': 'ZIP', 'version': '2.0.0', 'file_prefix': 'branding-mockup',
                'requirements': 'Adobe Photoshop CC 2020+',
                'support_duration': '۱ ماه',
                'update_duration': '',
                'sales': 456, 'views': 5890,
            },
            {
                'title': 'گیفت کارت گوگل پلی ۵۰۰ هزار تومانی',
                'slug': 'google-play-giftcard-500',
                'category': 'محصولات مجازی',
                'brand': 'انواتو',
                'product_type': 'virtual',
                'license_type': 'single',
                'price': 500000, 'old_price': None,
                'image': 'virtual-giftcard.png',
                'short_description': 'کد گیفت کارت گوگل پلی به ارزش ۵۰۰ هزار تومان؛ تحویل کد بلافاصله پس از پرداخت',
                'description': (
                    '<p>پس از پرداخت موفق، <b>کد فعال‌سازی گیفت کارت گوگل پلی</b> بلافاصله در بخش دانلودهای '
                    'پنل کاربری شما نمایش داده می‌شود.</p>'
                    '<ul><li>کد اصلی و تست‌شده</li>'
                    '<li>قابل استفاده در اکانت ایرانی گوگل پلی</li></ul>'
                ),
                'file_type': 'TXT', 'version': '', 'file_prefix': 'googleplay-giftcard',
                'requirements': 'اکانت گوگل پلی',
                'support_duration': '۷ روز',
                'update_duration': '',
                'is_unlimited': False, 'stock': 25,
                'sales': 892, 'views': 9450,
            },
            {
                'title': 'لایسنس یک‌ساله آنتی‌ویروس سگال',
                'slug': 'segal-antivirus-license',
                'category': 'محصولات مجازی',
                'brand': 'نرم‌افزاری آریا',
                'product_type': 'virtual',
                'license_type': 'subscription',
                'price': 1150000, 'old_price': 1400000,
                'image': 'virtual-antivirus.png',
                'short_description': 'لایسنس یک‌ساله آنتی‌ویروس ایرانی سگال برای یک سیستم؛ فعال‌سازی آنی',
                'description': (
                    '<p>لایسنس رسمی و یک‌ساله آنتی‌ویروس <b>سگال</b> شامل همه آپدیت‌ها و پشتیبانی تا پایان '
                    'دوره است. کد فعال‌سازی پس از خرید در پنل کاربری نمایش داده می‌شود.</p>'
                ),
                'file_type': 'TXT', 'version': '2026', 'file_prefix': 'segal-license',
                'requirements': 'ویندوز 10/11',
                'operating_system': 'ویندوز',
                'support_duration': '۱۲ ماه',
                'update_duration': '۱۲ ماه',
                'is_unlimited': False, 'stock': 40,
                'sales': 534, 'views': 6240,
            },
            {
                'title': 'اشتراک شش‌ماهه دستیار هوش مصنوعی پی‌آی‌بات',
                'slug': 'pybot-ai-subscription',
                'category': 'محصولات مجازی',
                'brand': 'استودیو راها',
                'product_type': 'virtual',
                'license_type': 'subscription',
                'price': 2100000, 'old_price': None,
                'image': 'virtual-ai.png',
                'short_description': 'اشتراک ۶ ماهه دستیار هوش مصنوعی فارسی برای تولید محتوا و پشتیبانی مشتریان',
                'description': (
                    '<p><b>پی‌آی‌بات</b> دستیار هوش مصنوعی فارسی است که برای تولید محتوا، پاسخ به مشتریان و '
                    'خلاصه‌سازی اسناد به کار می‌آید. با خرید این اشتراک، کد فعال‌سازی ۶ ماهه دریافت می‌کنید.</p>'
                    '<ul><li>پاسخ‌دهی فارسی روان</li>'
                    '<li>اتصال به وب سایت و شبکه‌های اجتماعی</li></ul>'
                ),
                'file_type': 'TXT', 'version': '2.0', 'file_prefix': 'pybot-subscription',
                'requirements': 'مرورگر یا اپلیکیشن موبایل',
                'support_duration': '۶ ماه',
                'update_duration': '۶ ماه',
                'sales': 211, 'views': 3890,
            },
        ]

        for data in products_data:
            product, created = Product.objects.get_or_create(
                slug=data['slug'],
                defaults={
                    'vendor': admin,
                    'title': data['title'],
                    'short_description': data['short_description'],
                    'description': data['description'],
                    'price': data['price'],
                    'old_price': data.get('old_price'),
                    'is_featured': data.get('featured', False),
                    'product_type': data['product_type'],
                    'license_type': data['license_type'],
                    'requirements': data.get('requirements', ''),
                    'operating_system': data.get('operating_system'),
                    'support_duration': data.get('support_duration', ''),
                    'update_duration': data.get('update_duration', ''),
                    'demo_url': data.get('demo_url', ''),
                    'documentation_url': data.get('documentation_url', ''),
                    'status': 'published',
                    'published_at': timezone.now(),
                    'views': data.get('views', 0),
                    'sales_count': data.get('sales', 0),
                    'is_unlimited': data.get('is_unlimited', True),
                    'stock_count': data.get('stock', 0) if not data.get('is_unlimited', True) else 0,
                },
            )
            if not created:
                continue

            product.category.add(categories[data['category']])
            product.brand.add(brands[data['brand']])

            # تصویر محصول
            image_path = os.path.join(PRODUCT_IMAGES, data['image'])
            if os.path.exists(image_path):
                with open(image_path, 'rb') as f:
                    product.image.save(data['image'], ImageFile(f), save=True)

            # فایل دیجیتال قابل دانلود
            zip_name = f"{data['file_prefix']}-v{data['version'] or '1.0'}.zip" if data['file_type'] == 'ZIP' else f"{data['file_prefix']}.txt"
            if data['file_type'] == 'TXT':
                content = ContentFile(
                    f"کد فعال‌سازی محصول «{data['title']}»\n\nCODE: {product.pid.upper()}-2026-FILEMARKET\n\n"
                    "این کد مخصوص حساب کاربری شما صادر شده است.\n".encode('utf-8'))
            else:
                content = make_zip(data['title'], {
                    'docs/INSTALL.md': '# راهنمای نصب\nاین فایل نمونه برای نمایش سیستم فروش فایل است.',
                    'src/app.php': '<?php\n// کد نمونه محصول\n',
                })
            DigitalAsset.objects.create(
                product=product,
                file_type=data['file_type'],
                version=data['version'],
                changelog=data.get('changelog', ''),
            ).file.save(zip_name, content, save=True)

            self.stdout.write(self.style.SUCCESS(f'محصول ثبت شد: {data["title"]}'))

        # ------------------------------------------------------------------ بنرها
        banners_data = [
            ('اسلایدر ۱ - فروشگاه فایل', 'slider-1.png', 'main_slider', '/products/'),
            ('اسلایدر ۲ - قالب‌های وب سایت', 'slider-2.png', 'main_slider', '/products/category/html-templates/'),
            ('اسلایدر ۳ - خدمات طراحی سایت', 'slider-3.png', 'main_slider', '/services/'),
            ('فایل‌های طراحی و UI Kit', 'small-design-uikit.png', 'small_banner', '/products/category/design-files/'),
            ('محصولات مجازی و اشتراک‌ها', 'small-virtual-ai.png', 'small_banner', '/products/category/virtual-products/'),
            ('نرم‌افزار و ابزارهای کاربردی', 'small-software-tasks.png', 'small_banner', '/products/category/software-tools/'),
            ('تخفیف‌های ویژه فایل‌ها', 'small-design-mockup.png', 'small_banner', '/products/discount_product/'),
            ('قالب‌های آماده وب سایت', 'large-1.png', 'large_banner', '/products/category/html-templates/'),
            ('سفارش طراحی اختصاصی سایت', 'large-2.png', 'large_banner', '/services/'),
            ('همه فایل‌های فروشگاه', 'single-1.png', 'single_banner', '/products/'),
        ]
        for title, image, banner_type, url in banners_data:
            if Banner.objects.filter(title=title).exists():
                continue
            banner = Banner(title=title, url=url, banner_type=banner_type, status='published')
            image_path = os.path.join(BANNER_IMAGES, image)
            if os.path.exists(image_path):
                with open(image_path, 'rb') as f:
                    banner.image.save(image, ImageFile(f), save=True)
                    self.stdout.write(f'بنر ثبت شد: {title}')

        # ------------------------------------------------------------------ پکیج‌های طراحی سایت
        packages_data = [
            {
                'title': 'سایت شرکتی', 'subtitle': 'برای شرکت‌ها، هلدینگ‌ها و برندهای حرفه‌ای',
                'price': 25000000, 'delivery_days': 21, 'revisions': 3, 'is_featured': False, 'order': 1,
                'features': 'طراحی اختصاصی تا ۱۰ صفحه\nریسپانسیو کامل موبایل و تابلِت\nفرم تماس و درخواست مشاوره\nپنل مدیریت محتوای فارسی\nسئو پایه و اتصال به گوگل\nیک سال پشتیبانی رایگان\nآموزش کار با پنل',
            },
            {
                'title': 'فروشگاه اینترنتی', 'subtitle': 'فروش آنلاین محصول با درگاه پرداخت',
                'price': 45000000, 'delivery_days': 30, 'revisions': 4, 'is_featured': True, 'order': 2,
                'features': 'طراحی اختصاصی صفحات فروشگاه\nمدیریت نامحدود محصول و دسته‌بندی\nاتصال به درگاه پرداخت (زرین‌پال و ...)\nمدیریت موجودی و انبار\nسیستم کد تخفیف و باشگاه مشتریان\nاتصال به پست و باربری\nبخش وبلاگ و سئو فروشگاه\nیک سال پشتیبانی رایگان',
            },
            {
                'title': 'سایت شخصی و رزومه', 'subtitle': 'برای متخصص‌ها، فریلنسرها و هنرمندان',
                'price': 9000000, 'delivery_days': 10, 'revisions': 2, 'is_featured': False, 'order': 3,
                'features': 'طراحی مدرن تک‌صفحه‌ای یا چند صفحه‌ای\nبخش نمونه کارها و رزومه\nفرم تماس و شبکه‌های اجتماعی\nریسپانسیو کامل\n۶ ماه پشتیبانی رایگان',
            },
            {
                'title': 'پرتال سازمانی سفارشی', 'subtitle': 'اتوماسیون و پرتال اختصاصی سازمان شما',
                'price': None, 'delivery_days': 45, 'revisions': 5, 'is_featured': False, 'order': 4,
                'features': 'تحلیل و طراحی فرآیندهای سازمان\nتوسعه اختصاصی بر پایه جنگو/React\nتکمیل‌پذیری با نرم‌افزارهای داخلی\nدسترسی‌های سطح‌بندی شده کاربران\nقرارداد پشتیبانی سالانه\nآموزش تیم سازمان',
            },
        ]
        for data in packages_data:
            ServicePackage.objects.get_or_create(title=data['title'], defaults=data)

        portfolio_data = [
            ('وب سایت شرکتی آریا صنعت', 'corp-site.png', 'شرکتی', 'طراحی سایت شرکتی با بخش معرفی پروژه‌ها، اخبار و فرم استعلام قیمت.', 'https://example.com'),
            ('فروشگاه اینترنتی مُدلایف', 'shop-site.png', 'فروشگاهی', 'فروشگاه پوشاک با بیش از ۳۰۰۰ محصول، درگاه پرداخت و باشگاه مشتریان.', 'https://example.com'),
            ('وب سایت شخصی دکتر سارا محمدی', 'personal-site.png', 'شخصی', 'سایت رزومه و نوبت‌دهی آنلاین برای پزشک عمومی.', 'https://example.com'),
        ]
        for title, image, category, desc, url in portfolio_data:
            if PortfolioItem.objects.filter(title=title).exists():
                continue
            item = PortfolioItem(title=title, category=category, description=desc, url=url, order=portfolio_data.index((title, image, category, desc, url)) + 1)
            image_path = os.path.join(PORTFOLIO_IMAGES, image)
            if os.path.exists(image_path):
                with open(image_path, 'rb') as f:
                    item.image.save(image, ImageFile(f), save=True)
                    self.stdout.write(f'نمونه کار ثبت شد: {title}')

        # ------------------------------------------------------------------ مقالات وبلاگ
        article_cat, _ = ArticleCategory.objects.get_or_create(slug='learn-web', defaults={'title': 'آموزش طراحی وب'})
        seo_tag, _ = Tag.objects.get_or_create(slug='seo', defaults={'title': 'سئو'})
        articles_data = [
            {
                'slug': 'choose-wordpress-theme',
                'title': 'چطور قالب وردپرس مناسب کسب‌وکار خود را انتخاب کنیم؟',
                'description': (
                    '<p>انتخاب قالب وردپرس مناسب یکی از مهم‌ترین تصمیم‌ها در راه‌اندازی سایت است. در این مقاله '
                    'پنج معیار کلیدی را بررسی می‌کنیم: سرعت، سازگاری با افزونه‌های فارسی، به‌روزرسانی منظم، '
                    'پشتیبانی سازنده و ریسپانسیو بودن.</p><p>قبل از خرید هر قالبی حتماً دموی آن را روی موبایل '
                    'بررسی کنید و سرعت صفحه اصلی را با ابزارهای آنلاین بسنجید.</p>'
                ),
                'image': 'wp-corp-theme.png', 'views': 1250,
            },
            {
                'slug': 'digital-products-market-iran',
                'title': 'بازار محصولات دیجیتال در ایران؛ فرصت‌ها و چالش‌ها',
                'description': (
                    '<p>فروش فایل، قالب، نرم‌افزار و محصولات مجازی به یکی از پررونق‌ترین حوزه‌های کسب‌وکار '
                    'اینترنتی تبدیل شده است. مزیت اصلی این مدل کسب‌وکار، حذف هزینه ارسال و امکان فروش '
                    'نامحدود از یک فایل است.</p><p>در این مقاله نکات راه‌اندازی فروشگاه فایل از انتخاب '
                    'اسکریپت تا درگاه پرداخت را مرور می‌کنیم.</p>'
                ),
                'image': 'script-filesell.png', 'views': 980,
            },
            {
                'slug': 'site-speed-seo',
                'title': '۷ تکنیک عملی افزایش سرعت سایت برای سئوی بهتر',
                'description': (
                    '<p>سرعت بارگذاری یکی از فاکتورهای اصلی رتبه‌بندی گوگل است. فشرده‌سازی تصاویر، فعال‌سازی '
                    'کش مرورگر، حذف افزونه‌های اضافه، استفاده از CDN و بهینه‌سازی پایگاه داده از مهم‌ترین '
                    'اقدامات هستند.</p><p>در این مقاله هر مورد را گام‌به‌گام اجرا می‌کنیم.</p>'
                ),
                'image': 'plugin-seo.png', 'views': 1512,
            },
        ]
        for data in articles_data:
            if Article.objects.filter(slug=data['slug']).exists():
                continue
            article = Article(
                author=admin,
                title=data['title'],
                slug=data['slug'],
                description=data['description'],
                status='published',
                views=data['views'],
                meta_title=data['title'][:70],
                meta_description=data['title'][:160],
            )
            image_path = os.path.join(PRODUCT_IMAGES, data['image'])
            if os.path.exists(image_path):
                with open(image_path, 'rb') as f:
                    article.image.save(data['image'], ImageFile(f), save=True)
            article.category.add(article_cat)
            article.tags.add(seo_tag)
            self.stdout.write(f'مقاله ثبت شد: {data["title"]}')

        # ------------------------------------------------------------------ کامنت نمونه
        first_product = Product.objects.filter(slug='shopino-woocommerce-theme').first()
        if first_product and not ProductComment.objects.filter(product=first_product).exists():
            ProductComment.objects.create(
                product=first_product, author=demo,
                body='قالب واقعاً حرفه‌ای و سبک است. مستندات نصب هم خیلی کامل بود و در چند ساعت فروشگاه‌مان راه افتاد. ممنون از پشتیبانی سریع.',
                status='published',
            )

        # ------------------------------------------------------------------ صفحات ثابت
        pages_data = [
            {
                'slug': 'قوانین-و-مقررات',
                'title': 'قوانین و مقررات',
                'summary': 'قوانین استفاده از سرویس‌های فروشگاه فایل‌مارکت',
                'content': (
                    '<p>با ثبت‌نام و استفاده از سایت، شما شرایط زیر را می‌پذیرید:</p>'
                    '<ul><li>فایل‌های خریداری‌شده فقط برای استفاده شخصی یا تجاریِ اعلام‌شده در لایسنس مجازند و '
                    'بازفروش یا انتشار مجدد آن‌ها ممنوع است.</li>'
                    '<li>لینک دانلود هر فایل تا ۷ روز و حداکثر ۵ بار قابل استفاده است.</li>'
                    '<li>در صورت مغایرت فایل با توضیحات ارائه‌شده، تا ۷ روز امکان درخواست بازگشت وجه وجود دارد.</li>'
                    '<li>لایسنس محصولات مجازی (گیفت کارت و اشتراک) پس از نمایش کد فعال‌سازی قابل بازگشت نیست.</li></ul>'
                ),
            },
            {
                'slug': 'سوالات-متداول',
                'title': 'سوالات متداول',
                'summary': 'پاسخ پرسش‌های رایج درباره خرید و دانلود فایل',
                'content': (
                    '<h3>پس از پرداخت چطور فایل را دریافت کنم؟</h3>'
                    '<p>بلافاصله پس از پرداخت موفق، لینک دانلود در همان صفحه نمایش داده می‌شود و همیشه از بخش '
                    '«دانلودهای من» در پنل کاربری در دسترس است.</p>'
                    '<h3>اگر لینک دانلود منقضی شد چه کنم؟</h3>'
                    '<p>از طریق صفحه تماس با ما درخواست تمدید بدهید؛ برای مشکلات فنی تمدد رایگان انجام می‌شود.</p>'
                    '<h3>فایل‌ها لایسنس دارند؟</h3>'
                    '<p>بله؛ نوع لایسنس هر فایل در صفحه محصول درج شده و در فایل خریداری‌شده نیز گواهی لایسنس قرار دارد.</p>'
                ),
            },
            {
                'slug': 'راهنمای-خرید',
                'title': 'راهنمای خرید',
                'summary': 'مراحل خرید و دانلود فایل از فایل‌مارکت',
                'content': (
                    '<p>خرید از فایل‌مارکت فقط سه مرحله دارد:</p>'
                    '<ol><li>ورود به حساب کاربری و افزودن فایل‌های مورد نظر به سبد خرید</li>'
                    '<li>پرداخت آنلاین از طریق درگاه امن بانکی</li>'
                    '<li>دانلود فوری فایل‌ها از صفحه سفارش یا بخش «دانلودهای من»</li></ol>'
                    '<p>برای مشاهده لینک دانلود، نیازی به مرحله اضافه‌ای نیست؛ همه‌چیز خودکار انجام می‌شود.</p>'
                ),
            },
        ]
        for data in pages_data:
            StaticPage.objects.get_or_create(slug=data['slug'], defaults=data)

        # ------------------------------------------------------------------ تنظیمات درگاه‌های پرداخت
        gateways_data = [
            ('zarinpal', 'زرین‌پال', True, 'پرداخت امن با تمام کارت‌های عضو شتاب'),
            ('snappay', 'اسنپ‌پی', False, 'پرداخت اقساطی اسنپ‌پی'),
            ('torobpay', 'ترب‌پی', False, 'پرداخت از طریق ترب'),
        ]
        for key, title, enabled, description in gateways_data:
            GatewaySettings.objects.get_or_create(
                key=key,
                defaults={'title': title, 'is_enabled': enabled, 'description': description},
            )
        self.stdout.write('تنظیمات درگاه‌های پرداخت ثبت شد (زرین‌پال فعال؛ مرچنت کد را از پنل مدیریت وارد کنید).')

        # ------------------------------------------------------------------ ریدایرکت‌های نمونه
        from core.models import Redirect
        sample_redirects = [
            ('/shop/', '/products/', 'نمونه: مسیر قدیمی فروشگاه'),
            ('/faq/', '/pages/سوالات-متداول/', 'نمونه: مسیر کوتاه سوالات متداول'),
            ('/about-us/', '/about/', 'نمونه: مسیر قدیمی درباره ما'),
            ('/blog/posts/', '/blog/', 'نمونه: مسیر قدیمی وبلاگ'),
        ]
        for old, new, note in sample_redirects:
            Redirect.objects.get_or_create(old_path=old, defaults={'new_path': new, 'status_code': '301', 'is_active': True, 'note': note})
        self.stdout.write('ریدایرکت‌های نمونه ثبت شد (قابل مدیریت از پنل → ریدایرکت‌ها).')

        # ------------------------------------------------------------------ کد تخفیف خوش‌آمدگویی
        from datetime import timedelta
        if not Coupon.objects.filter(code='WELCOME10').exists():
            Coupon.objects.create(
                code='WELCOME10', discount_type='percentage', discount_value=10,
                max_usage=100, valid_from=timezone.now(),
                valid_to=timezone.now() + timedelta(days=90),
                maximum_discount=500000, minimum_order_amount=500000,
            )
            self.stdout.write('کد تخفیف WELCOME10 ثبت شد (۱۰٪ تا سقف ۵۰۰ هزار تومان).')

        # ------------------------------------------------- سفارش پرداخت‌شده نمونه + لینک دانلود
        # بدون این بخش، صفحه «فاکتور سفارش» و «دانلودهای من» هیچ داده‌ای برای
        # نمایش ندارند و عملاً قابل مشاهده نیستند.
        from downloads.models import DownloadToken

        if not Order.objects.filter(user=demo).exists():
            demo_products = list(
                Product.objects.filter(status='published', digital_asset__isnull=False)[:2]
            ) or list(Product.objects.filter(status='published')[:2])
            if demo_products:
                total = sum(p.price for p in demo_products)
                order = Order.objects.create(
                    user=demo,
                    total_price=total,
                    coupon_discount=0,
                    shipping_cost=0,
                    final_price=total,
                    status='paid',
                    items_data={
                        'items': [
                            {'product_id': p.id, 'title': p.title, 'quantity': 1, 'price': p.price}
                            for p in demo_products
                        ],
                        'coupon': None,
                        'discount': 0,
                    },
                )
                for p in demo_products:
                    OrderItem.objects.create(
                        order=order, product=p,
                        unit_price=p.price, quantity=1, total_price=p.price,
                    )
                    DownloadToken.objects.create(user=demo, product=p, order=order)
                self.stdout.write(
                    f'سفارش پرداخت‌شده نمونه ثبت شد: {order.order_number} '
                    f'({len(demo_products)} فایل قابل دانلود برای کاربر demo).'
                )

        self.stdout.write(self.style.SUCCESS(
            'داده‌های نمونه با موفقیت ثبت شد!\n'
            'ورود مدیر: admin / admin1234 (پنل مدیریت: /admin-panel/)\n'
            'ورود کاربر نمونه: demo / demo1234'
        ))
