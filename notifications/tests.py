from unittest.mock import patch

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from cart.models import Order
from core.http import HttpResult
from core.models import ContactUs
from product.models import Product, ProductComment
from services.models import ServiceRequest

from .email_backend import ConfigurableEmailBackend
from .models import AdminNotification, EmailSettings, SmsSettings
from .sms import SmsError, SmsIrClient, normalize_mobile


class NotificationEventTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user('notif-customer', password='Safe-pass-123!')
        AdminNotification.objects.all().delete()  # the user sign-up itself is an event

    def test_paid_order_creates_one_notification(self):
        order = Order.objects.create(user=self.customer, total_price=1000, final_price=1000, status='pending')
        self.assertFalse(AdminNotification.objects.filter(kind='order_paid').exists())
        order.status = 'paid'
        order.save()
        order.save()  # saved again by staff: no duplicate alert
        notes = AdminNotification.objects.filter(kind='order_paid')
        self.assertEqual(notes.count(), 1)
        self.assertIn(order.order_number, notes.get().title)
        self.assertEqual(notes.get().url, reverse('admin:cart_order_change', args=[order.pk]))

    def test_service_and_consultation_requests(self):
        ServiceRequest.objects.create(full_name='علی', phone='09120000000', message='سایت فروشگاهی', project_type='فروشگاه')
        ServiceRequest.objects.create(full_name='سارا', phone='09120000001', message='مشاوره می‌خواهم')
        kinds = sorted(AdminNotification.objects.values_list('kind', flat=True))
        self.assertEqual(kinds, ['consultation', 'service_request'])

    def test_contact_message_and_pending_comment(self):
        ContactUs.objects.create(first_name='رضا', last_name='محمدی', phone='0912', message='سلام')
        product = Product.objects.create(vendor=self.customer, title='فایل', slug='notif-file', price=1000)
        ProductComment.objects.create(product=product, author=self.customer, body='عالی')
        ProductComment.objects.create(product=product, author=self.customer, body='منتشر', status='published')
        self.assertEqual(AdminNotification.objects.filter(kind='contact').count(), 1)
        self.assertEqual(AdminNotification.objects.filter(kind='comment').count(), 1)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', SITE_URL='https://shop.example.test')
class NotificationDeliveryTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user('delivery-customer', password='Safe-pass-123!')

    def test_email_goes_to_configured_admins(self):
        config = EmailSettings.load()
        config.admin_recipients = 'owner@example.test,\nops@example.test'
        config.save()
        with self.captureOnCommitCallbacks(execute=True):
            ServiceRequest.objects.create(full_name='علی', phone='0912', message='یک سایت', project_type='شرکتی')
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ['owner@example.test', 'ops@example.test'])
        self.assertIn('درخواست طراحی سایت', message.subject)
        self.assertIn('https://shop.example.test/admin/services/servicerequest/', message.body)
        self.assertTrue(AdminNotification.objects.get(kind='service_request').emailed)

    def test_disabled_event_sends_no_email(self):
        config = EmailSettings.load()
        config.admin_recipients = 'owner@example.test'
        config.notify_contact = False
        config.save()
        with self.captureOnCommitCallbacks(execute=True):
            ContactUs.objects.create(first_name='a', last_name='b', phone='1', message='m')
        self.assertEqual(mail.outbox, [])

    def test_sms_alert_uses_bulk_line_and_normalised_numbers(self):
        config = SmsSettings.load()
        config.is_enabled = True
        config.api_key = 'KEY'
        config.line_number = '30001234'
        config.admin_mobiles = '+98 912 111 2233\n۰۹۱۲۴۴۴۵۵۶۶'
        config.save()
        reply = HttpResult(200, {'status': 1, 'message': 'موفق', 'data': {'packId': 'x'}}, '')
        order = Order.objects.create(user=self.customer, total_price=5000, final_price=5000, status='pending')
        with patch('notifications.sms.http_json', return_value=reply) as api, \
                self.captureOnCommitCallbacks(execute=True):
            order.status = 'paid'
            order.save()
        method, url = api.call_args.args
        body = api.call_args.kwargs['json_body']
        self.assertEqual((method, url), ('POST', 'https://api.sms.ir/v1/send/bulk'))
        self.assertEqual(api.call_args.kwargs['headers'], {'X-API-KEY': 'KEY'})
        self.assertEqual(body['lineNumber'], 30001234)
        self.assertEqual(body['mobiles'], ['09121112233', '09124445566'])
        self.assertTrue(AdminNotification.objects.get(kind='order_paid').sms_sent)

    def test_a_broken_mail_server_never_breaks_the_request(self):
        config = EmailSettings.load()
        config.admin_recipients = 'owner@example.test'
        config.save()
        with patch('notifications.services.send_mail', side_effect=OSError('smtp down')), \
                self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(reverse('services:request_service'), {
                'full_name': 'علی رضایی', 'phone': '09121234567', 'message': 'یک سایت فروشگاهی می‌خواهم.',
            })
        self.assertIn(response.status_code, (200, 302))
        self.assertFalse(AdminNotification.objects.get(kind='consultation').emailed)


class SmsClientTests(TestCase):
    def test_normalize_mobile(self):
        self.assertEqual(normalize_mobile('+989121234567'), '09121234567')
        self.assertEqual(normalize_mobile('00989121234567'), '09121234567')
        self.assertEqual(normalize_mobile('989121234567'), '09121234567')
        self.assertEqual(normalize_mobile('9121234567'), '09121234567')
        self.assertEqual(normalize_mobile('۰۹۱۲۱۲۳۴۵۶۷'), '09121234567')
        self.assertEqual(normalize_mobile('02112345678'), '')
        self.assertEqual(normalize_mobile('hello'), '')

    def test_verify_payload_and_error_message(self):
        reply = HttpResult(200, {'status': 1, 'data': {'messageId': 1, 'cost': 1.0}}, '')
        with patch('notifications.sms.http_json', return_value=reply) as api:
            SmsIrClient('KEY').send_verify('09121234567', 123456, {'CODE': '12345'})
        body = api.call_args.kwargs['json_body']
        self.assertEqual(body, {'mobile': '09121234567', 'templateId': 123456,
                                'parameters': [{'name': 'CODE', 'value': '12345'}]})
        refused = HttpResult(401, {'status': 0, 'message': 'کلید وب سرویس نامعتبر است'}, '')
        with patch('notifications.sms.http_json', return_value=refused):
            with self.assertRaisesMessage(SmsError, 'کلید وب سرویس نامعتبر است'):
                SmsIrClient('BAD').send_verify('09121234567', 1, {'CODE': '1'})


class EmailBackendTests(TestCase):
    @override_settings(EMAIL_FALLBACK_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_falls_back_to_environment_backend(self):
        from django.core.mail.backends.locmem import EmailBackend as LocMem

        backend = ConfigurableEmailBackend()
        self.assertIsInstance(backend._resolve(), LocMem)

    def test_uses_admin_smtp_settings_when_enabled(self):
        from django.core.mail.backends.smtp import EmailBackend as Smtp

        config = EmailSettings.load()
        config.is_enabled = True
        config.host = 'mail.example.ir'
        config.port = 465
        config.security = 'ssl'
        config.username = 'info@example.ir'
        config.password = 'PW'
        config.from_name = 'فروشگاه'
        config.save()
        backend = ConfigurableEmailBackend()
        smtp = backend._resolve()
        self.assertIsInstance(smtp, Smtp)
        self.assertEqual((smtp.host, smtp.port, smtp.use_ssl, smtp.use_tls, smtp.username, smtp.password),
                         ('mail.example.ir', 465, True, False, 'info@example.ir', 'PW'))
        self.assertIn('info@example.ir', backend._sender)


class AdminSettingsAndBellTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('bell-admin', 'admin@example.test', 'Safe-pass-123!')
        self.client.force_login(self.admin)

    def test_smtp_password_is_write_only_and_test_mail_is_sent(self):
        config = EmailSettings.load()
        config.password = 'STORED-PW'
        config.save()
        url = reverse('admin:notifications_emailsettings_change', args=[config.pk])
        page = self.client.get(url)
        self.assertNotContains(page, 'STORED-PW')
        self.assertContains(page, 'تنظیم شده')
        from django.core.mail.backends.locmem import EmailBackend as LocMem

        with patch('notifications.admin.smtp_backend_from_settings', return_value=LocMem()):
            response = self.client.post(url, {
                'is_enabled': 'on', 'host': 'mail.example.ir', 'port': 587, 'security': 'tls',
                'username': 'info@example.ir', 'password': '', 'from_email': '', 'from_name': '', 'timeout': 15,
                'admin_recipients': '', 'notify_order_paid': 'on', 'test_recipient': 'me@example.test',
            }, follow=True)
        self.assertContains(response, 'ایمیل آزمایشی به me@example.test ارسال شد')
        config.refresh_from_db()
        self.assertEqual(config.password, 'STORED-PW')
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['me@example.test'])

    def test_settings_changelist_opens_the_single_row(self):
        response = self.client.get(reverse('admin:notifications_smssettings_changelist'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/change/', response['Location'])

    def test_bell_feed_open_and_mark_all_read(self):
        AdminNotification.objects.all().delete()
        first = AdminNotification.objects.create(kind='contact', title='پیام تازه', url='/admin/core/contactus/')
        AdminNotification.objects.create(kind='comment', title='دیدگاه تازه')
        page = self.client.get(reverse('admin:index'))
        self.assertContains(page, 'data-fm-bell')
        self.assertContains(page, 'پیام تازه')
        feed = self.client.get(reverse('admin:notifications_adminnotification_feed')).json()
        self.assertEqual(feed['unread'], 2)
        response = self.client.get(reverse('admin:notifications_adminnotification_open', args=[first.pk]))
        self.assertRedirects(response, '/admin/core/contactus/', fetch_redirect_response=False)
        first.refresh_from_db()
        self.assertTrue(first.is_read)
        self.client.post(reverse('admin:notifications_adminnotification_mark_all_read'))
        self.assertFalse(AdminNotification.objects.filter(is_read=False).exists())

    def test_open_never_redirects_off_site(self):
        note = AdminNotification.objects.create(kind='system', title='x', url='//evil.example/')
        response = self.client.get(reverse('admin:notifications_adminnotification_open', args=[note.pk]))
        self.assertEqual(response['Location'], reverse('admin:notifications_adminnotification_change', args=[note.pk]))

    def test_customers_do_not_get_the_feed(self):
        customer = User.objects.create_user('feed-customer', password='Safe-pass-123!')
        self.client.force_login(customer)
        response = self.client.get(reverse('admin:notifications_adminnotification_feed'))
        self.assertEqual(response.status_code, 302)  # admin login redirect
