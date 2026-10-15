"""منوی همبرگری موبایل و منوی کناری صفحه‌ها به‌صورت کشو.

رفتار تعاملی (باز/بسته‌شدن، فوکوس، Esc، کشیدن انگشت، پوشیده‌نشدن زیر هدر) با
Chromium در ۳۲۰ و ۳۷۵ پیکسل بررسی شده است؛ این تست‌ها جلوی برگشتن ساختار و
اصلاح‌های ریشه‌ای را می‌گیرند.
"""
import re
from html.parser import HTMLParser
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from blog.models import Article, Category
from core.templatetags.custom_filters import tel_href
from core.tests_features import settings_row
from pages.models import StaticPage
from product.models import Product, ProductBrand, ProductCategory
from product.views import _active_filter_count

STATIC = Path(settings.BASE_DIR) / 'static'
VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'source', 'track', 'wbr'}


def _css(name):
    return re.sub(r'/\*.*?\*/', '', (STATIC / 'css' / name).read_text(encoding='utf-8'), flags=re.S)


class _Balance(HTMLParser):
    """Tracks open tags so a missing </aside> or </details> fails the test."""

    def __init__(self):
        super().__init__()
        self.stack, self.errors = [], []

    def handle_starttag(self, tag, attrs):
        if tag not in VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        if tag in self.stack:
            while self.stack and self.stack[-1] != tag:
                self.errors.append(f'unclosed <{self.stack.pop()}> before </{tag}>')
            self.stack.pop()
        else:
            self.errors.append(f'stray </{tag}>')


def _element(html, element_id):
    """The opening tag of the element with ``element_id``."""
    match = re.search(r'<[a-z]+[^>]*\sid="%s"[^>]*>' % re.escape(element_id), html)
    return match.group(0) if match else ''


class MainMobileMenuTests(TestCase):
    def setUp(self):
        settings_row(phone1='۰۲۱-۹۱۰۰ ۸۰۸۰')

    def test_hamburger_menu_is_a_drawer_not_a_bootstrap_collapse(self):
        html = self.client.get('/').content.decode()
        panel = _element(html, 'navigation')
        self.assertIn('data-fm-drawer', panel)
        self.assertIn('data-fm-drawer-media="(max-width: 1077.98px)"', panel)
        self.assertIn('data-fm-drawer-root-class="nav-open"', panel)
        # Bootstrap's .collapse hid the panel and delayed closing; the closed panel
        # also stayed focusable with Tab.
        self.assertNotIn('collapse navbar-collapse', panel)
        self.assertNotIn('data-target="#navigation"', html)
        self.assertRegex(html, r'<button class="navbar-toggler[^"]*" type="button" data-fm-drawer-open="navigation"')
        self.assertIn('class="fm-mnav__close" data-fm-drawer-close', html)

    def test_menu_is_grouped_and_has_theme_and_support_rows(self):
        html = self.client.get('/').content.decode()
        for label in ('فروشگاه', 'خدمات طراحی سایت', 'راهنما و ارتباط با ما'):
            self.assertIn(f'>{label}</p>', html)
        self.assertIn(reverse('pages:detail', args=['راهنمای-خرید']), html)
        self.assertIn(reverse('pages:detail', args=['سوالات-متداول']), html)
        self.assertIn('data-fm-theme-toggle', html)
        # The dialer needs Latin digits even when the number is stored in Persian.
        self.assertIn('href="tel:02191008080"', html)

    def test_signed_in_menu_has_account_shortcuts_and_staff_panel_link(self):
        user = User.objects.create_user('menu-user', password='Safe-pass-123!')
        self.client.force_login(user)
        html = self.client.get('/').content.decode()
        quick = re.search(r'<div class="fm-mnav__quick">(.*?)</div>', html, re.S).group(1)
        for name in ('dashboard:my_downloads', 'dashboard:orders', 'dashboard:wishlist_products', 'cart:cart'):
            self.assertIn(f'href="{reverse(name)}"', quick)
        self.assertNotIn('fm-mnav__staff', html)
        user.is_staff = True
        user.save()
        self.assertIn(f'href="{reverse("admin_home")}" class="fm-mnav__staff"', self.client.get('/').content.decode())

    def test_current_page_is_marked_in_the_menu(self):
        StaticPage.objects.create(title='راهنمای خرید', slug='راهنمای-خرید', content='<p>x</p>', layout='sidebar')
        html = self.client.get(reverse('pages:detail', args=['راهنمای-خرید'])).content.decode()
        self.assertRegex(html, r'href="%s" aria-current="page" class="is-active"' % re.escape(reverse('pages:detail', args=['راهنمای-خرید'])))

    def test_drawer_assets_load_before_the_night_layer_and_js_flag_is_set_early(self):
        html = self.client.get('/').content.decode()
        self.assertRegex(html, r'css/fm-drawers\.css\?v=[0-9a-f]{10}')
        self.assertRegex(html, r'js/fm-drawers\.js\?v=[0-9a-f]{10}')
        self.assertLess(html.index('css/fm-ui-audit.css?v='), html.index('css/fm-drawers.css?v='))
        self.assertLess(html.index('css/fm-drawers.css?v='), html.index('css/fm-dark.css?v='))
        # Without the class the side columns stay in the page (no-JS fallback).
        self.assertLess(html.index("classList.add('fm-js')"), html.index('</head>'))
        self.assertLess(html.index('js/fm-drawers.js?v='), html.index('js/store-actions.js?v='))


class TelHrefFilterTests(TestCase):
    def test_normalises_persian_digits_and_separators(self):
        self.assertEqual(tel_href('۰۲۱-۹۱۰۰ ۸۰۸۰'), 'tel:02191008080')
        self.assertEqual(tel_href('+98 912 000 1122'), 'tel:+989120001122')
        self.assertEqual(tel_href('٠٩١٢'), 'tel:0912')

    def test_empty_or_digitless_values_give_no_link(self):
        for value in (None, '', 'تماس بگیرید'):
            self.assertEqual(tel_href(value), '')


class ShopFilterDrawerTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('vendor', password='Safe-pass-123!')
        self.category = ProductCategory.objects.create(title='قالب‌ها', slug='themes')
        self.brand = ProductBrand.objects.create(title='انواتو', slug='envato')
        self.cheap = Product.objects.create(vendor=self.user, title='قالب ارزان', slug='cheap', price=1000,
                                            old_price=2000, status='published', product_type='template')
        self.pricey = Product.objects.create(vendor=self.user, title='افزونه گران', slug='pricey', price=9000,
                                             status='published', product_type='plugin')
        for product in (self.cheap, self.pricey):
            product.category.add(self.category)
            product.brand.add(self.brand)

    def _pages(self):
        return [
            reverse('product:product_list'),
            reverse('product:category_product_list', args=['themes']),
            reverse('product:brand_product_list', args=['envato']),
            reverse('product:discount_product'),
            reverse('product:product_search') + '?search=قالب',
        ]

    def test_every_shop_listing_has_the_filter_drawer(self):
        for url in self._pages():
            with self.subTest(url=url):
                html = self.client.get(url).content.decode()
                aside = _element(html, 'fm-shop-filters')
                self.assertIn('class="sidebar-page col-12 col-lg-3 fm-side"', aside)
                self.assertIn('data-fm-drawer-media="(max-width: 991.98px)"', aside)
                self.assertIn('aria-labelledby="fm-shop-filters-title"', aside)
                self.assertIn('data-fm-drawer-open="fm-shop-filters"', html)
                self.assertIn('fm-side-toggle-wrap fm-side-toggle-wrap--sticky', html)
                self.assertIn('id="fm-shop-filters-title"', html)
                self.assertRegex(html, r'<div class="fm-side__actions">\s*<button type="submit" class="view_more')
                # The sidebar no longer takes a third of tablets beside the products.
                self.assertNotIn('col-md-4 col-lg-3', html)
                self.assertIn('<div class="col-12 col-lg-9">', html)
                checker = _Balance()
                checker.feed(html)
                self.assertEqual(checker.errors, [])

    def test_toggle_shows_result_count_and_active_filter_badge(self):
        url = reverse('product:product_list')
        html = self.client.get(url).content.decode()
        self.assertIn('<small>۲ فایل</small>', html)
        self.assertNotIn('fm-side-toggle__badge', html)
        self.assertNotIn('fm-side__reset', html)
        html = self.client.get(url, {'type': 'template', 'instant': '1'}).content.decode()
        self.assertRegex(html, r'fm-side-toggle__badge">۲<')
        self.assertIn(f'class="fm-side__reset" href="{url}"', html)

    def test_full_price_range_is_not_counted_as_a_filter(self):
        url = reverse('product:product_list')
        html = self.client.get(url, {'min_price': '1000', 'max_price': '9000'}).content.decode()
        self.assertNotIn('fm-side-toggle__badge', html)
        html = self.client.get(url, {'min_price': '1000', 'max_price': '5000'}).content.decode()
        self.assertRegex(html, r'fm-side-toggle__badge">۱<')

    def test_search_reset_link_keeps_the_query(self):
        html = self.client.get(reverse('product:product_search'), {'search': 'قالب', 'type': 'template'}).content.decode()
        self.assertIn('?search=%D9%82%D8%A7%D9%84%D8%A8">حذف فیلترها</a>', html)

    def test_active_filter_count_helper(self):
        from django.test import RequestFactory

        prices = {'min': 1000, 'max': 9000}
        request = RequestFactory().get('/', {'min_price': '1000', 'max_price': '9000'})
        self.assertEqual(_active_filter_count(request, prices, [], [], None), 0)
        request = RequestFactory().get('/', {'min_price': '2000', 'max_price': 'abc'})
        self.assertEqual(_active_filter_count(request, prices, ['template'], ['3'], '1'), 4)
        empty = {'min': None, 'max': None}
        self.assertEqual(_active_filter_count(RequestFactory().get('/', {'min_price': '5'}), empty, [], [], None), 0)


class AccountMenuDrawerTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('drawer-user', password='Safe-pass-123!')
        self.client.force_login(self.user)

    def test_every_dashboard_page_has_one_account_menu_as_a_drawer(self):
        names = ['home', 'orders', 'my_downloads', 'orders_delivered', 'cart_summary', 'orders_cancelled',
                 'orders_return', 'wishlist_products', 'user_addresses', 'notifications', 'user_profile']
        for name in names:
            with self.subTest(page=name):
                response = self.client.get(reverse(f'dashboard:{name}'))
                self.assertEqual(response.status_code, 200)
                html = response.content.decode()
                aside = _element(html, 'fm-account-menu')
                self.assertIn('fm-side', aside)
                self.assertIn('aria-label="منوی حساب کاربری"', aside)
                self.assertIn('data-fm-drawer-open="fm-account-menu"', html)
                # The phone dropdown repeated the whole menu a second time.
                self.assertNotIn('responsive-profile-menu', html)
                self.assertEqual(html.count('class="fm-logout-form"'), 1)
                if name != 'user_addresses':   # آدرس‌ها آیتم جداگانه‌ای در منو ندارد
                    self.assertRegex(html, r'href="%s" class="dropdown-item active" aria-current="page"' % re.escape(reverse(f'dashboard:{name}')))

    def test_profile_edit_page_also_uses_the_drawer(self):
        html = self.client.get(reverse('dashboard:edit_profile', args=[self.user.username])).content.decode()
        self.assertIn('data-fm-drawer-open="fm-account-menu"', html)
        self.assertIn('class="fm-side__who"', html)


class BlogAndHelpPageDrawerTests(TestCase):
    def setUp(self):
        author = User.objects.create_user('author', password='Safe-pass-123!', is_staff=True)
        self.category = Category.objects.create(title='آموزش', slug='learn')
        self.article = Article.objects.create(author=author, title='مقاله نمونه', slug='sample', status='published',
                                              description='<p>متن</p>')
        self.article.category.add(self.category)

    def test_blog_sidebars_open_as_a_drawer(self):
        for url in (reverse('blog:article_list'), reverse('blog:article_category', args=['learn']),
                    reverse('blog:article_detail', args=['sample'])):
            with self.subTest(url=url):
                html = self.client.get(url).content.decode()
                aside = _element(html, 'fm-blog-side')
                self.assertTrue(aside.startswith('<aside class="col-12 col-lg-3'), aside)
                self.assertIn('data-fm-drawer', aside)
                self.assertIn('data-fm-drawer-open="fm-blog-side"', html)
                checker = _Balance()
                checker.feed(html)
                self.assertEqual(checker.errors, [])

    def test_help_pages_with_a_sidebar_get_the_drawer_and_others_do_not(self):
        StaticPage.objects.create(title='قوانین', slug='rules', content='<p>x</p>', layout='sidebar')
        StaticPage.objects.create(title='درباره', slug='wide', content='<p>x</p>', layout='wide')
        html = self.client.get(reverse('pages:detail', args=['rules'])).content.decode()
        self.assertIn('data-fm-drawer-open="fm-page-side"', html)
        self.assertIn('data-fm-drawer', _element(html, 'fm-page-side'))
        html = self.client.get(reverse('pages:detail', args=['wide'])).content.decode()
        self.assertNotIn('fm-page-side', html)


class AdminMenusTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('boss', 'boss@example.com', 'Safe-pass-123!')
        self.client.force_login(self.admin)

    def test_staff_panel_drawer_can_be_closed_from_inside(self):
        html = self.client.get(reverse('admin_home')).content.decode()
        self.assertIn('id="ap-sidebar"', html)
        self.assertIn('aria-controls="ap-sidebar"', html)
        self.assertIn('class="ap-sidebar__close" type="button" data-ap-close-nav', html)

    @staticmethod
    def _drawer(html):
        start = html.index('<div class="fm-adm-drawer"')
        end = html.index('<div class="fm-adm-drawer__foot">', start)
        end = html.index('</div>', end) + len('</div>')        # پایان پاورقی کشو
        return html[start:html.index('</div>', end) + len('</div>')]

    def test_django_admin_has_a_mobile_drawer_with_quick_links_and_all_sections(self):
        for url in (reverse('admin:index'), reverse('admin:product_product_changelist')):
            with self.subTest(url=url):
                html = self.client.get(url).content.decode()
                self.assertIn('data-fm-adm-open aria-controls="fm-adm-drawer"', html)
                self.assertIn("classList.add('fm-adm-js')", html)
                # Desktop header keeps its nine links; the drawer has its own copy.
                self.assertEqual(html.count('class="fm-adm-quick-link"'), 9)
                drawer = self._drawer(html)
                self.assertIn(f'href="{reverse("admin:product_product_add")}"', drawer)
                self.assertIn('<details class="fm-adm-drawer__app"', drawer)
                checker = _Balance()
                checker.feed(drawer)
                self.assertEqual((checker.errors, checker.stack), ([], []))
        drawer = self._drawer(self.client.get(reverse('admin:product_product_changelist')).content.decode())
        self.assertRegex(drawer, r'<details class="fm-adm-drawer__app" open>\s*<summary>')
        self.assertIn(f'href="{reverse("admin:product_product_changelist")}" aria-current="page"', drawer)

    def test_changelist_filter_becomes_a_drawer_on_phones(self):
        # Django renders the filter panel; the button and close control are added by
        # fm-admin.js so the admin templates stay untouched.
        html = self.client.get(reverse('admin:product_product_changelist')).content.decode()
        self.assertIn('id="changelist-filter"', html)
        script = (STATIC / 'js' / 'fm-admin.js').read_text(encoding='utf-8')
        self.assertIn("document.getElementById('changelist-filter')", script)
        self.assertIn("toggle.setAttribute('aria-controls', 'changelist-filter')", script)
        css = _css('fm-admin.css')
        self.assertIn('html.fm-adm-js #content #changelist-filter {', css)
        self.assertIn('html.fm-adm-js #content #changelist-filter.is-open {', css)
        self.assertIn('html.fm-adm-js .fm-adm-filter-toggle {', css)

    def test_admin_login_page_has_no_drawer(self):
        self.client.logout()
        html = self.client.get(reverse('admin:login')).content.decode()
        self.assertNotIn('fm-adm-drawer', html)


class RootCauseFixTests(TestCase):
    def test_entrance_animation_does_not_leave_a_transform_behind(self):
        # fill-mode «both» kept transform:translateY(0) on every main .container,
        # which made it the containing block of position:fixed drawers.
        css = _css('modern-2026.css')
        self.assertRegex(css, r'main \.container, main \.container-fluid \{ animation: fmFadeUp \.45s ease backwards; \}')
        self.assertNotRegex(css, r'fmFadeUp[^;]*\bboth\b')

    def test_body_is_not_a_scroll_container_so_sticky_works(self):
        css = _css('fm-drawers.css')
        self.assertRegex(css, r'@supports \(overflow-x: clip\) \{\s*html, body \{ overflow-x: clip; \}')
        self.assertIn('html.fm-drawer-active .wrapper.default { z-index: auto; }', css)

    def test_side_drawers_only_apply_with_js_and_below_desktop(self):
        css = _css('fm-drawers.css')
        block = css[css.index('@media (max-width: 991.98px)'):]
        self.assertIn('.fm-js .fm-side {', block)
        self.assertIn('.fm-js .fm-side-toggle-wrap {', block)
        # Token rule: the button background token is never used as a text colour.
        self.assertIsNone(re.search(r'(?<![-\w])color:\s*var\(--fm-action-bg', css))

    def test_account_menu_is_not_hidden_at_exactly_992px(self):
        css = _css('fm-accessibility.css')
        self.assertNotIn('max-width: 992px', css)
        self.assertNotIn('.profile-page-aside .profile-menu { display: none; }', css)

    def test_closed_mobile_menu_is_hidden_from_keyboard(self):
        css = _css('fm-drawers.css')
        closed = re.search(r'\.sidebar-collapse nav\.header-responsive \.navbar-collapse \{([^}]*)\}', css).group(1)
        self.assertIn('visibility: hidden;', closed)

    def test_admin_palette_also_applies_when_day_theme_is_chosen_explicitly(self):
        css = _css('fm-admin.css')
        self.assertIn(":root, html[data-theme='light'] {", css)

    def test_old_collapse_glue_is_gone_and_drawers_close_each_other(self):
        main = (STATIC / 'js' / 'main.js').read_text(encoding='utf-8')
        self.assertNotIn(".collapse('hide')", main)
        self.assertNotIn('fm-mobile-nav-backdrop', main)
        store = (STATIC / 'js' / 'store-actions.js').read_text(encoding='utf-8')
        self.assertIn('window.FMDrawers.close(', store)
        self.assertIn('window.FMCloseCartDrawer = function', store)
        drawers = (STATIC / 'js' / 'fm-drawers.js').read_text(encoding='utf-8')
        self.assertIn('window.FMDrawers = {', drawers)
        self.assertIn("event.key === 'Escape'", drawers)
