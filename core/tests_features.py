"""قابلیت‌های فروشگاه: شبکه‌های اجتماعی، بنرها، ویترین‌ها، بلوک‌های HTML، صفحه‌ها،
مگامنو، آیکن‌های هدر، اشتراک‌گذاری، سبد خرید و دیدگاه‌ها."""
import json
import shutil
import tempfile
from datetime import timedelta

from django.contrib.auth.models import Permission, User
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from cart.models import Cart, CartItem
from core.models import Banner, HtmlBlock, SiteSettings
from core.social import social_links
from core.validators import validate_site_link
from dashboard.models import Wishlist
from pages.models import StaticPage
from product.models import Product, ProductCategory, ProductComment, ProductShowcase, ProductShowcaseItem

def _png_bytes():
    from io import BytesIO

    from PIL import Image

    buffer = BytesIO()
    Image.new('RGB', (8, 4), (20, 120, 130)).save(buffer, format='PNG')
    return buffer.getvalue()


PNG = _png_bytes()


def settings_row(**fields):
    row = SiteSettings.objects.order_by('pk').first() or SiteSettings.objects.create(copy_right='©')
    for key, value in fields.items():
        setattr(row, key, value)
    row.save()
    return row


class SocialLinksTests(TestCase):
    def test_placeholders_handles_and_unsafe_values(self):
        row = settings_row(instagram_link='https://instagram.com/username', telegram_link='@my_channel',
                           twitter_link='javascript:alert(1)', eitaa_link='eitaa.com/shop', bale_link='')
        links = {item['key']: item['url'] for item in social_links(row)}
        self.assertNotIn('instagram', links)
        self.assertEqual(links['telegram'], 'https://t.me/my_channel')
        self.assertNotIn('x', links)
        self.assertEqual(links['eitaa'], 'https://eitaa.com/shop')
        self.assertNotIn('bale', links)

    def test_footer_and_contact_show_global_and_iranian_networks(self):
        settings_row(instagram_link='https://instagram.com/shop', aparat_link='https://www.aparat.com/shop',
                     rubika_link='https://rubika.ir/shop')
        home = self.client.get('/').content.decode()
        self.assertRegex(home, r'social-sprite\.svg\?v=[0-9a-f]{10}#si-instagram')
        self.assertRegex(home, r'social-sprite\.svg\?v=[0-9a-f]{10}#si-aparat')
        self.assertIn('پیام‌رسان‌ها و شبکه‌های ایرانی', home)
        # The old markup used «fa fa-instagram» (solid style) and never showed an icon.
        self.assertNotIn('fa fa-instagram', home)
        contact = self.client.get(reverse('core:contact'))
        self.assertContains(contact, 'https://rubika.ir/shop')
        self.assertContains(contact, 'روبیکا')


class SiteLinkValidatorTests(TestCase):
    def test_accepts_internal_paths_and_https(self):
        for value in ('/products/', 'https://example.ir/a?b=1', ''):
            validate_site_link(value)

    def test_rejects_scripts_and_protocol_relative(self):
        for value in ('javascript:alert(1)', '//evil.example', 'ftp://x.example', '/\\evil'):
            with self.assertRaises(ValidationError, msg=value):
                validate_site_link(value)


_MEDIA = tempfile.mkdtemp(prefix='fm-test-media-')


@override_settings(MEDIA_ROOT=_MEDIA)
class BannerAndShowcaseTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(_MEDIA, ignore_errors=True)

    def setUp(self):
        cache.clear()
        settings_row()
        self.vendor = User.objects.create_user('home-vendor', password='Safe-pass-123!', is_staff=True)

    def _banner(self, **fields):
        defaults = {'title': 'بنر', 'banner_type': 'small_banner',
                    'image': SimpleUploadedFile('b.png', PNG, content_type='image/png')}
        defaults.update(fields)
        return Banner.objects.create(**defaults)

    def test_banner_text_size_width_and_optional_link(self):
        self._banner(title='تخفیف پاییزه', subtitle='فقط این هفته', description='تا ۴۰٪', button_text='خرید',
                     display_size='lg', width='half', text_position='center', url='', open_in_new_tab=True)
        html = self.client.get('/').content.decode()
        self.assertIn('fm-banner--size-lg', html)
        self.assertIn('fm-banner--text-center', html)
        self.assertIn('col-12 col-md-6', html)
        self.assertIn('فقط این هفته', html)
        self.assertIn('تخفیف پاییزه', html)
        self.assertIn('<div class="fm-banner__link">', html)  # no URL: no dead anchor

    def test_banner_without_text_keeps_the_image_only_look(self):
        banner = self._banner(title='بنر ساده', url='/products/')
        self.assertFalse(banner.has_overlay)
        self.assertEqual(banner.column_class, 'col-6 col-lg-3')
        slider = self._banner(title='اسلاید', banner_type='main_slider')
        self.assertTrue(slider.has_overlay)
        self.assertTrue(slider.overlay_description)

    def test_side_carousel_is_not_empty_when_every_product_is_discounted(self):
        # Regression: #bid-s only listed products *without* an old price.
        for index in range(3):
            Product.objects.create(vendor=self.vendor, title=f'تخفیفی {index}', slug=f'disc-{index}',
                                   price=1000, old_price=2000, status='published')
        response = self.client.get('/')
        self.assertEqual(len(response.context['latest_products']), 3)
        self.assertContains(response, 'id="bid-s"')
        # The theme hid the whole column below 1078px, so phones/tablets never saw it.
        self.assertContains(response, 'class="col-3 fm-bid-col"')

    def test_manual_showcase_order_title_and_countdown(self):
        first = Product.objects.create(vendor=self.vendor, title='اول', slug='first', price=1, status='published')
        second = Product.objects.create(vendor=self.vendor, title='دوم', slug='second', price=1, status='published')
        draft = Product.objects.create(vendor=self.vendor, title='پیش‌نویس', slug='draft', price=1, status='draft')
        showcase = ProductShowcase.objects.get(placement='home_side')
        showcase.source, showcase.title = 'manual', 'پیشنهاد لحظه‌ای'
        showcase.ends_at = timezone.now() + timedelta(hours=5)
        showcase.save()
        ProductShowcaseItem.objects.create(showcase=showcase, product=second, order=1)
        ProductShowcaseItem.objects.create(showcase=showcase, product=first, order=2)
        ProductShowcaseItem.objects.create(showcase=showcase, product=draft, order=0)
        response = self.client.get('/')
        self.assertEqual([p.title for p in response.context['latest_products']], ['دوم', 'اول'])
        self.assertContains(response, 'پیشنهاد لحظه‌ای')
        self.assertContains(response, 'data-fm-countdown=')

    def test_inactive_or_expired_showcase_hides_the_section(self):
        Product.objects.create(vendor=self.vendor, title='x', slug='x', price=1, status='published')
        ProductShowcase.objects.filter(placement='home_side').update(is_active=False)
        self.assertNotContains(self.client.get('/'), 'id="bid-s"')
        ProductShowcase.objects.filter(placement='home_side').update(is_active=True,
                                                                     ends_at=timezone.now() - timedelta(minutes=1))
        self.assertNotContains(self.client.get('/'), 'id="bid-s"')

    def test_staff_get_edit_shortcuts_on_home_sections_and_customers_do_not(self):
        Product.objects.create(vendor=self.vendor, title='ویترین', slug='showcase-item', price=1000, status='published')
        self._banner(title='اسلاید', banner_type='main_slider')
        side = ProductShowcase.objects.get(placement='home_side')
        side_url = reverse('admin:product_productshowcase_change', args=[side.pk])
        slider_url = reverse('admin:core_banner_changelist') + '?banner_type__exact=main_slider'

        for client_user in (None, User.objects.create_user('buyer', password='Safe-pass-123!')):
            if client_user:
                self.client.force_login(client_user)
            html = self.client.get('/').content.decode()
            self.assertNotIn('fm-staff-edit', html)
            self.assertNotIn(side_url, html)

        # A staff member without the matching permission gets no dead link.
        self.client.force_login(self.vendor)
        self.assertNotIn('fm-staff-edit', self.client.get('/').content.decode())

        admin = User.objects.create_superuser('home-admin', 'a@example.com', 'Safe-pass-123!')
        self.client.force_login(admin)
        html = self.client.get('/').content.decode()
        self.assertIn(f'href="{side_url}"', html)
        self.assertIn(f'href="{slider_url}"', html)
        self.assertEqual(self.client.get(side_url).status_code, 200)
        self.assertEqual(self.client.get(slider_url).status_code, 200)


class HtmlCodeTests(TestCase):
    def setUp(self):
        cache.clear()
        settings_row()
        self.superuser = User.objects.create_superuser('html-admin', 'h@example.test', 'Safe-pass-123!')
        self.staff = User.objects.create_user('html-staff', password='Safe-pass-123!', is_staff=True)
        self.staff.user_permissions.add(*Permission.objects.filter(
            codename__in=['change_product', 'view_product', 'add_htmlblock', 'change_htmlblock', 'view_htmlblock']))

    def test_html_blocks_render_where_placed(self):
        HtmlBlock.objects.create(title='بنر', placement='home_middle', html='<div id="autumn-sale">جشنواره</div>')
        HtmlBlock.objects.create(title='خاموش', placement='home_middle', html='<div id="off-block"></div>', is_active=False)
        html = self.client.get('/').content.decode()
        self.assertIn('<div id="autumn-sale">جشنواره</div>', html)
        self.assertNotIn('off-block', html)

    def test_product_custom_html_modes(self):
        product = Product.objects.create(vendor=self.superuser, title='کد', slug='code', price=1, status='published',
                                         description='<p>متن ویرایشگر</p>', custom_html='<section id="custom-x">جدول</section>',
                                         custom_html_mode='replace')
        url = reverse('product:product_detail', args=[product.pid, product.slug])
        html = self.client.get(url).content.decode()
        self.assertIn('<section id="custom-x">جدول</section>', html)
        self.assertNotIn('<p>متن ویرایشگر</p>', html)
        Product.objects.filter(pk=product.pk).update(custom_html_mode='after')
        html = self.client.get(url).content.decode()
        self.assertLess(html.index('متن ویرایشگر'), html.index('custom-x'))

    def test_only_trusted_admins_can_edit_raw_html(self):
        product = Product.objects.create(vendor=self.superuser, title='p', slug='p', price=1)
        url = reverse('admin:product_product_change', args=[product.pk])
        self.client.force_login(self.staff)
        form = self.client.get(url).context['adminform'].form
        self.assertNotIn('custom_html', form.fields)
        self.assertEqual(self.client.get(reverse('admin:core_htmlblock_add')).status_code, 403)

        self.client.force_login(self.superuser)
        page = self.client.get(url)
        self.assertIn('custom_html', page.context['adminform'].form.fields)
        self.assertContains(page, 'data-fm-code-editor')
        self.assertContains(page, 'js/fm-code-editor.js')

        self.staff.user_permissions.add(Permission.objects.get(codename='edit_raw_html'))
        self.staff = User.objects.get(pk=self.staff.pk)
        self.client.force_login(self.staff)
        self.assertIn('custom_html', self.client.get(url).context['adminform'].form.fields)

    def test_page_layouts_and_staff_preview(self):
        page = StaticPage.objects.create(title='لندینگ', slug='landing', content='', layout='landing',
                                         custom_html='<main id="hero-html">سلام</main>', custom_html_mode='replace',
                                         is_published=False)
        url = reverse('pages:detail', args=[page.slug])
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_login(self.superuser)
        response = self.client.get(url)
        self.assertContains(response, '<main id="hero-html">سلام</main>')
        self.assertContains(response, 'fm-page--landing')
        self.assertContains(response, 'پیش‌نمایش مدیر')
        self.assertNotContains(response, 'صفحات راهنما')  # landing has no sidebar
        StaticPage.objects.filter(pk=page.pk).update(layout='sidebar', is_published=True, content='<p>راهنما</p>',
                                                    custom_html_mode='after')
        self.client.logout()
        response = self.client.get(url)
        self.assertContains(response, 'صفحات راهنما')
        self.assertContains(response, 'hero-html')


class HeaderMenuShareTests(TestCase):
    def setUp(self):
        cache.clear()
        settings_row()
        self.user = User.objects.create_user('header-user', password='Safe-pass-123!')
        self.category = ProductCategory.objects.create(title='قالب وردپرس', slug='wp', icon='fa-wordpress',
                                                       short_description='قالب‌های فروشگاهی')
        self.product = Product.objects.create(vendor=self.user, title='قالب آریا', slug='aria', price=1000,
                                              status='published')
        self.product.category.add(self.category)

    def test_header_uses_icons_with_counts(self):
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, product=self.product)
        Wishlist.objects.create(user=self.user, product=self.product)
        self.client.force_login(self.user)
        html = self.client.get('/').content.decode()
        self.assertIn('data-cart-count >1<', html.replace('data-cart-count  >', 'data-cart-count >'))
        self.assertIn('data-wishlist-count >1<', html.replace('data-wishlist-count  >', 'data-wishlist-count >'))
        self.assertIn('fa fa-cart-shopping', html)
        self.assertIn('fa fa-heart', html)
        self.assertNotIn('<span aria-hidden="true">حساب</span>', html)
        self.assertNotIn('<span aria-hidden="true">سبد</span>', html)

    def test_mega_menu_lists_categories_with_products_and_refreshes(self):
        html = self.client.get('/').content.decode()
        self.assertIn('fm-mega', html)
        self.assertIn('قالب‌های فروشگاهی', html)
        self.assertIn('قالب آریا', html)
        newer = Product.objects.create(vendor=self.user, title='قالب جدید پارسا', slug='parsa', price=5,
                                       status='published', is_featured=True)
        newer.category.add(self.category)
        self.assertIn('قالب جدید پارسا', self.client.get('/').content.decode())

    def test_mobile_menu_has_close_button_account_links_and_categories(self):
        html = self.client.get('/').content.decode()
        self.assertIn('class="fm-mnav__close"', html)
        self.assertIn('id="mobile-categories"', html)
        self.assertIn(reverse('account:register'), html)

    def test_product_and_article_pages_have_a_working_share_sheet(self):
        html = self.client.get(reverse('product:product_detail', args=[self.product.pid, self.product.slug])).content.decode()
        self.assertIn('id="fm-share-sheet"', html)
        self.assertIn('https://wa.me/?text=', html)
        self.assertIn('https://t.me/share/url?url=http%3A%2F%2Ftestserver%2Fproducts%2F', html)
        self.assertIn('data-share-instagram', html)
        self.assertNotIn('data-target="#myModal"', html)


class CartRobustnessTests(TestCase):
    def setUp(self):
        settings_row()
        self.user = User.objects.create_user('cart-user', password='Safe-pass-123!')
        self.product = Product.objects.create(vendor=self.user, title='فایل', slug='cart-file', price=1000,
                                              status='published')
        self.ajax = {'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest', 'HTTP_X_CURRENT_PATH': '/products/'}

    def test_expired_session_gets_json_401_not_a_login_page(self):
        # Account-only AJAX actions (the wishlist) still answer an expired
        # session with JSON instead of a login page.
        response = self.client.post(reverse('dashboard:add_to_wishlist', args=[self.product.pk]), '{}',
                                    content_type='application/json', **self.ajax)
        self.assertEqual(response.status_code, 401)
        data = response.json()
        self.assertTrue(data['login_required'])
        self.assertEqual(data['login_url'], reverse('account:login') + '?next=/products/')

    def test_guest_can_add_to_cart_without_an_account(self):
        response = self.client.post(reverse('cart:add_to_cart', args=[self.product.pk]), '{}',
                                    content_type='application/json', **self.ajax)
        self.assertEqual(response.status_code, 200)
        self.assertEqual((response.json()['success'], response.json()['cart_count']), (True, 1))

    def test_adding_twice_and_removing_twice_are_harmless(self):
        self.client.force_login(self.user)
        url = reverse('cart:add_to_cart', args=[self.product.pk])
        first = self.client.post(url, '{}', content_type='application/json', **self.ajax).json()
        second = self.client.post(url, '{}', content_type='application/json', **self.ajax)
        self.assertEqual((first['success'], first['cart_count']), (True, 1))
        self.assertEqual(second.status_code, 200)
        self.assertTrue(second.json()['already_in_cart'])
        item = CartItem.objects.get()
        remove = reverse('cart:remove_cart_item', args=[item.pk])
        self.assertEqual(self.client.post(remove, '{}', content_type='application/json', **self.ajax).json()['cart_count'], 0)
        again = self.client.post(remove, '{}', content_type='application/json', **self.ajax)
        self.assertEqual(again.status_code, 200)
        self.assertTrue(again.json()['already_removed'])

    def test_drawer_reports_count_and_unavailable_items(self):
        self.client.force_login(self.user)
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, product=self.product)
        Product.objects.filter(pk=self.product.pk).update(status='draft')
        drawer = self.client.get(reverse('cart:cart_drawer')).content.decode()
        self.assertIn('data-cart-count="1"', drawer)
        self.assertIn('دیگر قابل خرید نیست', drawer)
        page = self.client.get(reverse('cart:cart'))
        self.assertEqual(len(page.context['unavailable_items']), 1)
        self.assertContains(page, 'ابتدا فایل‌های ناموجود را حذف کنید')

    def test_wishlist_endpoints_return_the_new_count(self):
        self.client.force_login(self.user)
        added = self.client.post(reverse('dashboard:add_to_wishlist', args=[self.product.pk]), **self.ajax).json()
        self.assertEqual(added['wishlist_count'], 1)
        removed = self.client.post(reverse('dashboard:remove_from_wishlist', args=[self.product.pk]), **self.ajax).json()
        self.assertEqual(removed['wishlist_count'], 0)
        again = self.client.post(reverse('dashboard:remove_from_wishlist', args=[self.product.pk]), **self.ajax)
        self.assertEqual(again.status_code, 200)


class CommentModerationTests(TestCase):
    def setUp(self):
        settings_row()
        self.author = User.objects.create_user('commenter', password='Safe-pass-123!')
        self.other = User.objects.create_user('other-visitor', password='Safe-pass-123!')
        self.product = Product.objects.create(vendor=self.author, title='فایل نظر', slug='comment-file', price=1,
                                              status='published')
        self.url = reverse('product:product_detail', args=[self.product.pid, self.product.slug])

    def test_comment_is_saved_pending_and_visible_only_to_its_author(self):
        self.client.force_login(self.author)
        response = self.client.post(self.url, json.dumps({'body': 'خیلی کاربردی بود'}), content_type='application/json')
        data = response.json()
        self.assertEqual(data['status'], 'success')
        self.assertTrue(data['moderation'])
        comment = ProductComment.objects.get()
        self.assertEqual(comment.status, 'pending')
        page = self.client.get(self.url)
        self.assertContains(page, 'خیلی کاربردی بود')
        self.assertContains(page, 'در انتظار تأیید')
        self.client.force_login(self.other)
        self.assertNotContains(self.client.get(self.url), 'خیلی کاربردی بود')

    def test_admin_approve_action_publishes(self):
        comment = ProductComment.objects.create(product=self.product, author=self.author, body='منتظر تأیید')
        admin = User.objects.create_superuser('mod-admin', 'm@example.test', 'Safe-pass-123!')
        self.client.force_login(admin)
        changelist = self.client.get(reverse('admin:product_productcomment_changelist'))
        self.assertContains(changelist, '1 مورد در انتظار تأیید')
        self.client.post(reverse('admin:product_productcomment_changelist'),
                         {'action': 'approve', '_selected_action': [comment.pk]})
        comment.refresh_from_db()
        self.assertEqual(comment.status, 'published')
        self.client.logout()
        self.assertContains(self.client.get(self.url), 'منتظر تأیید')


class AssetVersionTests(TestCase):
    """CSS/JS URLs carry a content hash so a deploy is never served from a stale cache."""

    def setUp(self):
        from core import assets

        assets._locations.clear()
        self.addCleanup(assets._locations.clear)

    def test_url_has_a_content_hash_that_changes_with_the_file(self):
        import os
        import re

        from core.assets import asset_url

        folder = tempfile.mkdtemp(prefix='fm-assets-')
        self.addCleanup(shutil.rmtree, folder, True)
        os.makedirs(os.path.join(folder, 'js'))
        script = os.path.join(folder, 'js', 'probe.js')
        with open(script, 'w') as handle:
            handle.write('console.log(1);')
        with self.settings(STATICFILES_DIRS=[folder]):
            first = asset_url('js/probe.js')
            self.assertRegex(first, r'^/static/js/probe\.js\?v=[0-9a-f]{10}$')
            self.assertEqual(asset_url('js/probe.js'), first)  # stable while unchanged
            with open(script, 'w') as handle:
                handle.write('console.log("updated build");')
            second = asset_url('js/probe.js')
        self.assertNotEqual(first, second)
        self.assertTrue(re.match(r'^/static/js/probe\.js\?v=', second))
        # A file that cannot be found still gets its normal static URL.
        self.assertEqual(asset_url('js/does-not-exist.js'), '/static/js/does-not-exist.js')

    def test_pages_admin_and_service_worker_use_versioned_assets(self):
        html = self.client.get('/').content.decode()
        self.assertRegex(html, r'/static/js/store-actions\.js\?v=[0-9a-f]{10}')
        self.assertRegex(html, r'/static/css/fm-features\.css\?v=[0-9a-f]{10}')
        self.assertNotRegex(html, r'/static/js/store-actions\.js"')

        worker = self.client.get('/service-worker.js').content.decode()
        self.assertRegex(worker, r"/static/css/bootstrap\.min\.css\?v=[0-9a-f]{10}")
        self.assertIn('old.search !== url.search', worker)  # older copies are pruned

        admin = User.objects.create_superuser('asset-admin', 'asset@example.com', 'Safe-pass-123!')
        self.client.force_login(admin)
        page = self.client.get(reverse('admin:index')).content.decode()
        self.assertRegex(page, r'/static/css/fm-admin\.css\?v=[0-9a-f]{10}')
