"""ورود با پیامک (sms.ir) و نقش‌های فروشنده/نویسنده."""
import re
from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from accounts.models import PhoneOTP
from accounts.roles import AUTHOR_GROUP, VENDOR_GROUP
from core.http import HttpResult
from notifications.models import SmsSettings

SMS_OK = HttpResult(200, {'status': 1, 'message': 'موفق', 'data': {'messageId': 7, 'cost': 1.0}}, '')


class OtpLoginTests(TestCase):
    def setUp(self):
        cache.clear()
        config = SmsSettings.load()
        config.is_enabled = True
        config.api_key = 'SANDBOX-KEY'
        config.otp_login_enabled = True
        config.otp_template_id = 123456
        config.otp_parameter = 'CODE'
        config.save()
        self.url = reverse('account:otp_login')

    def _send(self, phone='09121234567'):
        with patch('notifications.sms.http_json', return_value=SMS_OK) as api:
            response = self.client.post(self.url, {'action': 'send', 'phone': phone})
        sent_code = None
        if api.called:
            sent_code = api.call_args.kwargs['json_body']['parameters'][0]['value']
        return response, sent_code, api

    def _verify(self, code):
        return self.client.post(self.url, {'action': 'verify', 'code': code})

    def test_page_is_unavailable_until_sms_is_configured(self):
        SmsSettings.objects.update(otp_login_enabled=False)
        response = self.client.get(self.url)
        self.assertRedirects(response, reverse('account:login'), fetch_redirect_response=False)
        self.assertNotContains(self.client.get(reverse('account:login')), reverse('account:otp_login'))

    def test_login_page_offers_mobile_login_when_configured(self):
        self.assertContains(self.client.get(reverse('account:login')), reverse('account:otp_login'))

    def test_code_is_sent_with_the_template_and_stored_hashed(self):
        response, code, api = self._send('+98 912 123 4567')
        self.assertRedirects(response, self.url, fetch_redirect_response=False)
        body = api.call_args.kwargs['json_body']
        self.assertEqual(api.call_args.args, ('POST', 'https://api.sms.ir/v1/send/verify'))
        self.assertEqual((body['mobile'], body['templateId'], body['parameters'][0]['name']), ('09121234567', 123456, 'CODE'))
        self.assertTrue(re.fullmatch(r'\d{5}', code))
        otp = PhoneOTP.objects.get()
        self.assertNotIn(code, otp.code_hash)
        self.assertEqual(self.client.session['otp_phone'], '09121234567')

    def test_new_number_creates_an_account_and_logs_in(self):
        _, code, _ = self._send()
        response = self._verify(code)
        self.assertRedirects(response, reverse('dashboard:home'), fetch_redirect_response=False)
        user = User.objects.get(profile__phone='09121234567')
        self.assertFalse(user.has_usable_password())
        self.assertEqual(int(self.client.session['_auth_user_id']), user.pk)
        self.assertTrue(PhoneOTP.objects.get().consumed_at)

    def test_existing_profile_phone_logs_into_that_account(self):
        user = User.objects.create_user('ali', password='Safe-pass-123!')
        user.profile.phone = '09121234567'
        user.profile.save()
        _, code, _ = self._send()
        self._verify(code)
        self.assertEqual(int(self.client.session['_auth_user_id']), user.pk)
        self.assertEqual(User.objects.count(), 1)

    def test_wrong_codes_are_limited_and_a_code_works_once(self):
        _, code, _ = self._send()
        wrong = '00000' if code != '00000' else '11111'
        for _ in range(5):
            response = self._verify(wrong)
            self.assertEqual(response.status_code, 400)
        response = self._verify(code)  # sixth attempt: the code is burnt
        self.assertEqual(response.status_code, 400)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_code_cannot_be_reused(self):
        _, code, _ = self._send()
        self._verify(code)
        self.client.logout()
        session = self.client.session
        session['otp_phone'] = '09121234567'
        session.save()
        response = self._verify(code)
        self.assertEqual(response.status_code, 400)

    def test_resend_cooldown_and_sms_failure(self):
        self._send()
        response, _, api = self._send()
        self.assertEqual(response.status_code, 400)
        api.assert_not_called()
        PhoneOTP.objects.all().delete()
        with patch('notifications.sms.http_json', return_value=HttpResult(400, {'status': 0, 'message': 'اعتبار کافی نیست'}, '')):
            response = self.client.post(self.url, {'action': 'send', 'phone': '09129999999'})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(PhoneOTP.objects.filter(phone='09129999999').exists())

    def test_inactive_and_ambiguous_numbers_are_refused(self):
        inactive = User.objects.create_user('inactive', password='Safe-pass-123!', is_active=False)
        inactive.profile.phone = '09121234567'
        inactive.profile.save()
        _, code, _ = self._send()
        self.assertEqual(self._verify(code).status_code, 400)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_invalid_number_is_rejected_without_sms(self):
        response, _, api = self._send('12345')
        self.assertEqual(response.status_code, 400)
        api.assert_not_called()


class RoleTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('role-admin', 'a@example.test', 'Safe-pass-123!')
        self.vendor = User.objects.create_user('vendor-user', password='Safe-pass-123!')
        self.author = User.objects.create_user('author-user', password='Safe-pass-123!')
        self.customer = User.objects.create_user('customer-user', password='Safe-pass-123!')
        self.vendor.groups.add(Group.objects.get(name=VENDOR_GROUP))
        self.author.groups.add(Group.objects.get(name=AUTHOR_GROUP))
        self.client.force_login(self.admin)

    def test_role_groups_exist_after_migrate(self):
        self.assertTrue(Group.objects.filter(name=VENDOR_GROUP).exists())
        self.assertTrue(Group.objects.filter(name=AUTHOR_GROUP).exists())

    def test_product_vendor_choices_are_staff_and_vendors_only(self):
        from product.admin import ProductAdminForm

        choices = set(ProductAdminForm().fields['vendor'].queryset.values_list('username', flat=True))
        self.assertEqual(choices, {'role-admin', 'vendor-user'})

    def test_existing_product_keeps_its_old_vendor(self):
        from product.admin import ProductAdminForm
        from product.models import Product

        product = Product.objects.create(vendor=self.customer, title='قدیمی', slug='legacy', price=1)
        choices = set(ProductAdminForm(instance=product).fields['vendor'].queryset.values_list('username', flat=True))
        self.assertIn('customer-user', choices)

    def test_vendor_autocomplete_lists_only_allowed_users(self):
        response = self.client.get(reverse('admin:autocomplete'), {
            'app_label': 'product', 'model_name': 'product', 'field_name': 'vendor', 'term': 'user'})
        names = {item['text'] for item in response.json()['results']}
        self.assertEqual(names, {'vendor-user'})

    def test_article_author_choices(self):
        from blog.admin import ArticleAdminForm

        choices = set(ArticleAdminForm().fields['author'].queryset.values_list('username', flat=True))
        self.assertEqual(choices, {'role-admin', 'author-user'})

    def test_user_admin_role_actions(self):
        response = self.client.post(reverse('admin:auth_user_changelist'), {
            'action': 'make_vendor', '_selected_action': [self.customer.pk]})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(self.customer.groups.filter(name=VENDOR_GROUP).exists())
        page = self.client.get(reverse('admin:auth_user_changelist'), {'role': 'vendor'})
        listed = {user.username for user in page.context['cl'].result_list}
        self.assertEqual(listed, {'vendor-user', 'customer-user'})
