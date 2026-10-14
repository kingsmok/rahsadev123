import io

from PIL import Image

from core import validators as validate
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from cart.models import Order, OrderItem
from dashboard import analytics
from dashboard.models import Address, Wishlist
from payments.models import PaymentTransaction
from product.models import Product


class AccountDataRegressionTests(TestCase):
    """Coverage for the account forms used by the dashboard interface."""

    def setUp(self):
        self.user = User.objects.create_user('dashboard-user', password='Safe-pass-123!')
        self.address_url = reverse('dashboard:user_addresses')
        self.assertTrue(self.client.login(username='dashboard-user', password='Safe-pass-123!'))

    def address_payload(self, **overrides):
        payload = {
            'title': 'خانه',
            'full_address': 'تهران، خیابان نمونه، پلاک ۱',
            'city': 'تهران',
            'province': 'تهران',
            'postal_code': '1234567890',
            'receiver_name': 'کاربر آزمایشی',
            'phone_number': '09121234567',
        }
        payload.update(overrides)
        return payload

    def test_address_form_normalizes_local_digits_and_preserves_single_default(self):
        first = self.client.post(self.address_url, self.address_payload(is_default='on'))
        self.assertRedirects(first, self.address_url)

        second = self.client.post(self.address_url, self.address_payload(
            title='محل کار',
            postal_code='۱۲۳۴۵۶۷۸۹۰',
            phone_number='۰۹۱۲۱۲۳۴۵۶۷',
            is_default='on',
        ))
        self.assertRedirects(second, self.address_url)

        latest_address = Address.objects.get(title='محل کار')
        self.assertEqual(latest_address.postal_code, '1234567890')
        self.assertEqual(latest_address.phone_number, '09121234567')
        self.assertTrue(latest_address.is_default)
        self.assertEqual(Address.objects.filter(user=self.user, is_default=True).count(), 1)

    def test_invalid_address_keeps_values_and_reopens_the_modal(self):
        response = self.client.post(self.address_url, self.address_payload(postal_code='not-a-code'))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['show_address_modal'])
        self.assertContains(response, 'کد پستی باید فقط شامل اعداد باشد.')
        self.assertContains(response, "window.jQuery('#addressModal').modal('show')", html=False)
        self.assertEqual(Address.objects.count(), 0)

    def test_profile_can_clear_optional_fields_and_normalizes_numeric_input(self):
        profile = self.user.profile
        profile.first_name = 'نام قبلی'
        profile.last_name = 'نام خانوادگی'
        profile.email = 'old@example.test'
        profile.phone = '09121234567'
        profile.card_number = '5236'  # فقط ۴ رقم آخر نگه داشته می‌شود
        profile.about_me = 'متن قبلی'
        profile.save()

        edit_url = reverse('dashboard:edit_profile', args=[self.user.username])
        cleared = self.client.post(edit_url, {
            'first_name': '', 'last_name': '', 'email': '', 'phone': '',
            'card_number': '', 'about_me': '',
        })
        self.assertRedirects(cleared, reverse('dashboard:user_profile'))

        profile.refresh_from_db()
        self.user.refresh_from_db()
        self.assertEqual(profile.first_name, '')
        self.assertEqual(profile.phone, '')
        self.assertEqual(profile.card_number, '')
        self.assertEqual(self.user.email, '')

        normalized = self.client.post(edit_url, {
            'first_name': 'کاربر', 'last_name': 'تست', 'email': 'customer@example.test',
            'phone': '۰۹۱۲۱۲۳۴۵۶۷', 'card_number': '۶۰۳۷۴۹۸۵۱۴۷۸۵۲۳۶', 'about_me': '',
        })
        self.assertRedirects(normalized, reverse('dashboard:user_profile'))
        profile.refresh_from_db()
        self.assertEqual(profile.phone, '09121234567')
        self.assertEqual(profile.card_number, '5236')
        profile_page = self.client.get(reverse('dashboard:user_profile'))
        self.assertContains(profile_page, '**** **** **** 5236')
        self.assertNotContains(profile_page, '6037498514785236')

    def test_cancellation_request_is_digital_only_and_has_a_non_javascript_fallback(self):
        profile = self.user.profile
        profile.card_number = '5236'
        profile.save()
        url = reverse('dashboard:orders_return')

        shipped = Order.objects.create(
            user=self.user, total_price=1000, final_price=1000, status='shipped',
        )
        rejected = self.client.post(url, {'order_number': shipped.order_number}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(rejected.status_code, 200)
        self.assertFalse(rejected.json()['success'])
        self.assertIn('پرداخت‌شده', rejected.json()['message'])
        shipped.refresh_from_db()
        self.assertEqual(shipped.status, 'shipped')

        paid = Order.objects.create(
            user=self.user, total_price=1000, final_price=1000, status='paid',
        )
        accepted = self.client.post(url, {'order_number': paid.order_number}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertTrue(accepted.json()['success'])
        paid.refresh_from_db()
        self.assertEqual(paid.status, 'processing')

        pending = Order.objects.create(
            user=self.user, total_price=1000, final_price=1000, status='pending',
        )
        fallback = self.client.post(url, {'order_number': pending.order_number})
        self.assertRedirects(fallback, url)
        pending.refresh_from_db()
        self.assertEqual(pending.status, 'processing')

    def test_wishlist_removal_is_post_only_and_returns_ajax_feedback(self):
        product = Product.objects.create(
            vendor=self.user, title='فایل مورد علاقه', slug='favorite-file',
            description='توضیحات آزمایشی', price=1000, stock_count=1,
        )
        Wishlist.objects.create(user=self.user, product=product)
        url = reverse('dashboard:remove_from_wishlist', args=[product.id])

        self.assertEqual(self.client.get(url).status_code, 405)
        response = self.client.post(url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'success')
        self.assertFalse(Wishlist.objects.filter(user=self.user, product=product).exists())


class AdminPanelTests(TestCase):
    """پنل اختصاصی مدیریت: دسترسی، آمار، نمودارها و خروجی CSV."""

    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_user('panel-staff', password='Staff-pass-123!', is_staff=True)
        cls.customer = User.objects.create_user('panel-customer', password='Customer-pass-1!')
        cls.vendor = User.objects.create_user('panel-vendor', password='Vendor-pass-123!')
        cls.product = Product.objects.create(
            vendor=cls.vendor, title='قالب فروشگاهی نمونه', slug='sample-shop-theme',
            description='توضیحات', price=450000, stock_count=2, is_unlimited=False,
        )
        cls.paid_order = Order.objects.create(
            user=cls.customer, total_price=450000, final_price=450000, status='paid',
        )
        OrderItem.objects.create(
            order=cls.paid_order, product=cls.product, title_snapshot=cls.product.title,
            unit_price=450000, quantity=1, total_price=450000,
        )
        cls.pending_order = Order.objects.create(
            user=cls.customer, total_price=120000, final_price=120000, status='pending',
        )

    def setUp(self):
        self.panel_url = reverse('admin_home')
        self.assertTrue(self.client.login(username='panel-staff', password='Staff-pass-123!'))

    def test_panel_is_staff_only(self):
        self.client.logout()
        anonymous = self.client.get(self.panel_url)
        self.assertEqual(anonymous.status_code, 302)
        self.assertIn('/admin/login/', anonymous['Location'])

        self.client.login(username='panel-customer', password='Customer-pass-1!')
        self.assertEqual(self.client.get(self.panel_url).status_code, 302)

    def test_dashboard_reports_paid_revenue_and_ships_chart_data(self):
        response = self.client.get(self.panel_url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'dashboard/admin_home.html')
        self.assertEqual(response.context['kpis']['revenue'], 450000)
        self.assertEqual(response.context['kpis']['paid_orders'], 1)
        self.assertEqual(response.context['kpis']['all_orders'], 2)
        chart_data = response.context['chart_data']
        self.assertEqual(sum(chart_data['revenue']['values']), 450000)
        self.assertEqual(len(chart_data['revenue']['labels']), analytics.DEFAULT_RANGE_DAYS)
        self.assertContains(response, 'chart.umd.min.js')
        self.assertContains(response, 'ap-chart-data')

    def test_invalid_range_falls_back_to_the_default_window(self):
        response = self.client.get(self.panel_url, {'range': '999'})
        self.assertEqual(response.context['range_days'], analytics.DEFAULT_RANGE_DAYS)

        short = self.client.get(self.panel_url, {'range': '7'})
        self.assertEqual(short.context['range_days'], 7)
        self.assertEqual(len(short.context['revenue_series']), 7)

    def test_low_stock_products_are_flagged(self):
        self.assertIn(self.product, analytics.low_stock_products())

    def test_health_page_lists_incomplete_products(self):
        response = self.client.get(reverse('admin_health'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'dashboard/admin_health.html')
        self.assertIn(self.product, list(response.context['products_without_asset']))

    def test_orders_csv_export_has_bom_and_one_row_per_order(self):
        response = self.client.get(reverse('admin_export_orders'), {'range': '30'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv; charset=utf-8')
        self.assertIn('attachment', response['Content-Disposition'])
        content = response.content.decode('utf-8')
        self.assertTrue(content.startswith('\ufeff'))
        lines = content.strip().splitlines()
        self.assertEqual(len(lines), 3)  # سرتیتر + دو سفارش
        self.assertIn(self.paid_order.order_number, content)
        self.assertIn(self.pending_order.order_number, content)

    def test_revenue_series_ignores_unpaid_orders(self):
        series = analytics.revenue_series(7)
        self.assertEqual(sum(point['revenue'] for point in series), 450000)
        self.assertEqual(sum(point['orders'] for point in series), 1)

    def test_kpi_delta_is_none_without_a_previous_period(self):
        kpis = analytics.kpis(30)
        self.assertIsNone(kpis['deltas']['revenue'])


class AdminIndexBrandingTests(TestCase):
    """ادمین جنگو باید با برند و نوار شاخص فایل‌مارکت باز شود."""

    def setUp(self):
        self.staff = User.objects.create_user('branding-staff', password='Staff-pass-123!', is_staff=True)
        self.assertTrue(self.client.login(username='branding-staff', password='Staff-pass-123!'))

    def test_admin_index_uses_the_custom_theme_and_stats_bar(self):
        response = self.client.get(reverse('admin:index'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'admin/index.html')
        self.assertContains(response, 'fm-admin.css')
        self.assertContains(response, 'fm-admin-stats')
        self.assertContains(response, 'مدیریت فایل‌مارکت')
        self.assertContains(response, reverse('admin_home'))

    def test_admin_login_page_keeps_the_brand(self):
        self.client.logout()
        response = self.client.get(reverse('admin:login'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'fm-admin.css')

    def test_admin_pages_do_not_print_template_comments(self):
        # کامنت‌های چندخطیِ {# … #} در admin/base_site.html خام بالای همهٔ صفحات
        # ادمین (از جمله صفحهٔ ورود) چاپ می‌شدند و <head> را زودتر از موعد می‌بستند.
        responses = [self.client.get(reverse('admin:index'))]
        self.client.logout()
        responses.append(self.client.get(reverse('admin:login')))
        for response in responses:
            self.assertNotContains(response, '{#')
            self.assertNotContains(response, '#}')
            self.assertContains(response, '<h1 id="site-name">')


class ProfileImageSizeLimitTests(TestCase):
    """A customer's avatar upload must be bounded in size."""

    def setUp(self):
        self.user = User.objects.create_user('avatar-user', password='Safe-pass-123!')
        self.client.force_login(self.user)
        self.url = f'/dashboard/profile/{self.user.username}/'

    @staticmethod
    def _png(width=8, height=8):
        buffer = io.BytesIO()
        Image.new('RGB', (width, height), 'red').save(buffer, format='PNG')
        return buffer.getvalue()

    def test_normal_avatar_is_accepted(self):
        upload = SimpleUploadedFile('ok.png', self._png(), content_type='image/png')
        response = self.client.post(self.url, {'image': upload})

        self.user.profile.refresh_from_db()
        self.assertTrue(self.user.profile.image)
        self.assertNotIn('image', (response.context['form'].errors if response.context else {}))

    def test_oversized_avatar_is_rejected(self):
        payload = self._png()
        # Pad past the limit without breaking the PNG: trailing bytes after the
        # IEND chunk are ignored by decoders, so the file is still a valid image.
        oversized = SimpleUploadedFile(
            'huge.png', payload + b'\x00' * validate.MAX_IMAGE_UPLOAD_BYTES,
            content_type='image/png',
        )
        response = self.client.post(self.url, {'image': oversized})

        self.user.profile.refresh_from_db()
        self.assertFalse(self.user.profile.image)
        errors = response.context['form'].errors if response.context else {}
        self.assertIn('image', errors)

    def test_limit_message_names_the_allowed_size(self):
        oversized = SimpleUploadedFile(
            'huge2.png', self._png() + b'\x00' * validate.MAX_IMAGE_UPLOAD_BYTES,
            content_type='image/png',
        )
        response = self.client.post(self.url, {'image': oversized})

        errors = response.context['form'].errors if response.context else {}
        self.assertIn('مگابایت', str(errors.get('image', '')))


class AdminReconciliationQueueTests(TestCase):
    """Verified-but-undelivered payments must stand apart from real declines."""

    def setUp(self):
        self.staff = User.objects.create_user(
            'recon-staff', password='Staff-pass-123!', is_staff=True,
        )
        self.client.force_login(self.staff)
        self.count = 0

    def _transaction(self, raw_response, status='failed'):
        """Build a transaction on its own fresh order, product, buyer and vendor."""
        self.count += 1
        buyer = User.objects.create_user(f'recon-buyer-{self.count}', password='Safe-pass-123!')
        vendor = User.objects.create_user(f'recon-vendor-{self.count}', password='Safe-pass-123!')
        product = Product.objects.create(
            vendor=vendor, title=f'فایل {self.count}', slug=f'recon-f-{self.count}',
            description='توضیح', price=50000,
        )
        order = Order.objects.create(
            user=buyer, total_price=50000, coupon_discount=0, shipping_cost=0,
            final_price=50000, status='processing',
            items_data={'items': [{'product_id': product.pk, 'title': product.title,
                                   'quantity': 1, 'price': 50000}], 'coupon': None},
        )
        return PaymentTransaction.objects.create(
            order=order, gateway='zarinpal', amount=50000, authority=f'AUTH-{self.count}',
            status=status, raw_response=raw_response,
        )

    def test_undelivered_payment_is_listed_separately_from_a_decline(self):
        undelivered = self._transaction({
            'ref_id': 'REF-123', 'error': 'سفارش در وضعیت «در حال پردازش» است', 'unfulfilled': True,
        })
        declined = self._transaction({'error': 'کاربر از پرداخت انصراف داد'})

        response = self.client.get('/admin-panel/health/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'نیازمند رفع اختلاف مالی')
        # The reconciliation card carries the money-taken payment and its ref id.
        self.assertEqual([t.pk for t in response.context['unfulfilled_payments']], [undelivered.pk])
        self.assertContains(response, 'REF-123')
        # The plain decline appears only in the ordinary failed list.
        self.assertIn(declined.pk, [t.pk for t in response.context['failed_payments']])
        self.assertNotIn(declined.pk, [t.pk for t in response.context['unfulfilled_payments']])

    def test_empty_reconciliation_queue_says_so(self):
        response = self.client.get('/admin-panel/health/')
        self.assertEqual(len(response.context['unfulfilled_payments']), 0)
        self.assertContains(response, 'تأییدشده و تحویل‌نشده‌ای وجود ندارد')


class CustomerDashboardConsistencyTests(TestCase):
    """Dashboard counters and lists must agree with the pages they summarise."""

    def setUp(self):
        from datetime import timedelta

        from django.utils import timezone

        self.user = User.objects.create_user('dash-consistency', password='Safe-pass-123!')
        self.others = [User.objects.create_user(f'dash-other-{i}', password='Safe-pass-123!') for i in range(3)]
        self.timedelta, self.timezone = timedelta, timezone
        self.client.force_login(self.user)

    def test_notification_badge_matches_the_notifications_page(self):
        from dashboard.models import Notification

        broadcast = Notification.objects.create(message='برای همه', is_for_all_users=True)
        broadcast.users.set([self.user, *self.others])  # used to be counted once per listed user
        Notification.objects.create(
            message='منقضی', is_for_all_users=True,
            expiration_date=self.timezone.now() - self.timedelta(days=1),
        )
        Notification.objects.create(message='غیرفعال', is_for_all_users=True, is_active=False)
        personal = Notification.objects.create(message='شخصی')
        personal.users.set([self.user])

        badge = self.client.get(reverse('dashboard:home')).context['user_notifications_count']
        listed = list(self.client.get(reverse('dashboard:notifications')).context['notifications'])

        self.assertEqual(badge, 2)
        self.assertEqual(len(listed), 2)

    def test_popular_products_include_unlimited_licences(self):
        unlimited = Product.objects.create(
            vendor=self.user, title='نامحدود', slug='unlimited-popular', description='-', price=1000,
            is_unlimited=True, stock_count=0, views=50,
        )
        sold_out = Product.objects.create(
            vendor=self.user, title='تمام‌شده', slug='soldout-popular', description='-', price=1000,
            is_unlimited=False, stock_count=0, views=99,
        )

        popular = list(self.client.get(reverse('dashboard:home')).context['popular_products'])

        self.assertIn(unlimited, popular)
        self.assertNotIn(sold_out, popular)

    def test_a_paid_digital_order_counts_as_completed(self):
        paid = Order.objects.create(user=self.user, total_price=1000, final_price=1000, status='paid')
        Order.objects.create(user=self.user, total_price=1000, final_price=1000, status='pending')

        home = self.client.get(reverse('dashboard:home'))
        completed = self.client.get(reverse('dashboard:orders_delivered'))

        self.assertEqual(home.context['delivered_orders'], 1)
        self.assertEqual([order.pk for order in completed.context['orders']], [paid.pk])

    def test_malformed_address_ids_are_404_not_500(self):
        for field in ('delete_address', 'set_default'):
            response = self.client.post(reverse('dashboard:user_addresses'), {field: 'abc'})
            self.assertEqual(response.status_code, 404, field)


class AdminPanelCountersTests(TestCase):
    """Staff counters must not mix charged-but-undelivered payments with declines."""

    setUp = AdminReconciliationQueueTests.setUp
    _transaction = AdminReconciliationQueueTests._transaction

    def test_an_undelivered_payment_is_not_also_listed_or_counted_as_failed(self):
        undelivered = self._transaction({'ref_id': 'REF-9', 'error': 'x', 'unfulfilled': True})
        declined = self._transaction({'error': 'انصراف'})
        bare_decline = self._transaction({})

        health = self.client.get('/admin-panel/health/')
        failed_ids = [t.pk for t in health.context['failed_payments']]
        self.assertNotIn(undelivered.pk, failed_ids)
        self.assertCountEqual(failed_ids, [declined.pk, bare_decline.pk])

        home = self.client.get('/admin-panel/')
        self.assertEqual(home.context['kpis']['failed_payments'], 2)
        self.assertEqual(home.context['pending']['failed_payments'], 2)
        self.assertEqual(home.context['pending']['unfulfilled_payments'], 1)
        self.assertContains(home, 'پرداختِ تأییدشده و تحویل‌نشده')

    def test_comments_awaiting_moderation_are_counted_and_linked(self):
        from product.models import ProductComment

        self._transaction({})
        product = Product.objects.first()
        ProductComment.objects.create(product=product, author=self.staff, body='در انتظار')  # default: pending
        ProductComment.objects.create(product=product, author=self.staff, body='منتشر', status='published')

        home = self.client.get('/admin-panel/')

        self.assertEqual(home.context['pending']['pending_comments'], 1)
        self.assertContains(home, 'productcomment/?status__exact=pending')

    def test_order_export_runs_a_constant_number_of_queries(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        def export_queries():
            with CaptureQueriesContext(connection) as ctx:
                response = self.client.get('/admin-panel/export/orders/?range=365')
            self.assertEqual(response.status_code, 200)
            return len(ctx.captured_queries), response.content.decode('utf-8')

        paid = self._transaction({'ref_id': 'REF-A'}, status='paid')
        Order.objects.filter(pk=paid.order_id).update(status='paid')
        PaymentTransaction.objects.filter(pk=paid.pk).update(ref_id='REF-A')
        baseline, _ = export_queries()
        for _ in range(4):
            self._transaction({}, status='paid')
        queries, body = export_queries()

        self.assertEqual(queries, baseline)
        self.assertIn('REF-A', body)
