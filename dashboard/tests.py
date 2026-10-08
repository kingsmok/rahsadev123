from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from cart.models import Order, OrderItem
from dashboard import analytics
from dashboard.models import Address, Wishlist
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
        profile.card_number = '6037498514785236'
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
        self.assertEqual(profile.card_number, '6037498514785236')
        profile_page = self.client.get(reverse('dashboard:user_profile'))
        self.assertContains(profile_page, '**** **** **** 5236')
        self.assertNotContains(profile_page, '6037498514785236')

    def test_cancellation_request_is_digital_only_and_has_a_non_javascript_fallback(self):
        profile = self.user.profile
        profile.card_number = '6037498514785236'
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
