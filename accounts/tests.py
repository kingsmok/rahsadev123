from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Profile


@override_settings(
    LOGIN_RATE_LIMIT_WINDOW_SECONDS=60,
    LOGIN_RATE_LIMIT_IDENTITY_ATTEMPTS=2,
    LOGIN_RATE_LIMIT_IP_ATTEMPTS=10,
)
class LoginThrottleTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user('throttle-user', password='Correct-pass-123!')
        self.url = reverse('account:login')

    def test_failed_attempts_are_throttled_and_success_clears_counter(self):
        first = self.client.post(self.url, {'username': self.user.username, 'password': 'wrong-password'})
        second = self.client.post(self.url, {'username': self.user.username, 'password': 'wrong-password'})
        blocked = self.client.post(self.url, {'username': self.user.username, 'password': 'wrong-password'})

        self.assertContains(first, 'نام کاربری یا رمز عبور نادرست است.')
        self.assertContains(second, 'نام کاربری یا رمز عبور نادرست است.')
        self.assertContains(blocked, 'تعداد تلاش‌های ناموفق زیاد است.')

        cache.clear()
        response = self.client.post(
            self.url,
            {'username': self.user.username, 'password': 'Correct-pass-123!'},
        )
        self.assertRedirects(response, reverse('core:home'))


class OrphanProfileTests(TestCase):
    """Users created outside the post_save signal must still work.

    ``bulk_create`` and data migrations do not send ``post_save``, so a Profile
    row can be missing.  Django updates ``last_login`` during authentication,
    which used to raise ``RelatedObjectDoesNotExist`` and lock the user out.
    """

    def test_user_without_profile_can_save_and_log_in(self):
        User.objects.bulk_create([User(username='bulk-user', is_active=True)])
        user = User.objects.get(username='bulk-user')
        self.assertFalse(hasattr(user, 'profile') or
                         Profile.objects.filter(user=user).exists())

        user.set_password('Safe-pass-123!')
        user.save(update_fields=['password'])
        self.assertTrue(Profile.objects.filter(user=user).exists())

        response = self.client.post(reverse('account:login'), {
            'username': 'bulk-user', 'password': 'Safe-pass-123!',
        })
        self.assertRedirects(response, reverse('core:home'))

    def test_profile_is_not_duplicated_for_existing_users(self):
        user = User.objects.create_user('normal-user', password='Safe-pass-123!')
        first_pk = Profile.objects.get(user=user).pk
        user.first_name = 'رضا'
        user.save(update_fields=['first_name'])
        self.assertEqual(Profile.objects.filter(user=user).count(), 1)
        self.assertEqual(Profile.objects.get(user=user).pk, first_pk)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class PasswordResetFlowTests(TestCase):
    """بازیابی رمز عبور: از درخواست تا ورود با رمز جدید، بدون افشای وجود حساب."""

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            'reset-user', email='reset@example.com', password='Old-pass-123!',
        )
        self.url = reverse('account:password_reset')

    def _request_link(self, email='reset@example.com'):
        return self.client.post(self.url, {'email': email})

    def _extract_reset_path(self, message):
        import re

        match = re.search(r'/account/password-reset/confirm/\S+', message.body)
        self.assertIsNotNone(match, 'لینک بازیابی در متن ایمیل نیست')
        return match.group(0)

    def test_full_flow_changes_password_and_allows_login(self):
        from django.core import mail

        response = self._request_link()
        self.assertRedirects(response, reverse('account:password_reset_done'))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['reset@example.com'])

        confirm_path = self._extract_reset_path(mail.outbox[0])
        # GET روی لینک، توکن را در سشن می‌گذارد و به فرم تنظیم رمز می‌رود.
        confirm = self.client.get(confirm_path)
        self.assertEqual(confirm.status_code, 302)
        form_page = self.client.get(confirm.url)
        self.assertContains(form_page, 'تنظیم رمز جدید')

        done = self.client.post(confirm.url, {
            'new_password1': 'New-pass-456!',
            'new_password2': 'New-pass-456!',
        })
        self.assertRedirects(done, reverse('account:password_reset_complete'))

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('New-pass-456!'))
        self.assertFalse(self.user.check_password('Old-pass-123!'))

        login_response = self.client.post(reverse('account:login'), {
            'username': 'reset-user', 'password': 'New-pass-456!',
        })
        self.assertRedirects(login_response, reverse('core:home'))

    def test_unknown_email_sends_nothing_but_looks_identical(self):
        from django.core import mail

        response = self._request_link('nobody@example.com')
        self.assertRedirects(response, reverse('account:password_reset_done'))
        self.assertEqual(len(mail.outbox), 0)

    def test_tampered_token_is_rejected(self):
        from django.core import mail

        self._request_link()
        path = self._extract_reset_path(mail.outbox[0])
        tampered = path.rsplit('-', 1)[0] + '-deadbeef/'
        page = self.client.get(tampered)
        self.assertContains(page, 'نامعتبر یا منقضی')

    def test_pages_render(self):
        for name in ('account:password_reset', 'account:password_reset_done',
                     'account:password_reset_complete'):
            with self.subTest(url=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    PASSWORD_RESET_RATE_LIMIT_WINDOW_SECONDS=3600,
    PASSWORD_RESET_RATE_LIMIT_IDENTITY_ATTEMPTS=3,
    PASSWORD_RESET_RATE_LIMIT_IP_ATTEMPTS=10,
)
class PasswordResetThrottleTests(TestCase):
    def setUp(self):
        cache.clear()
        User.objects.create_user('throttled', email='t@example.com', password='Pass-12345!')
        self.url = reverse('account:password_reset')

    def test_fourth_request_is_silently_dropped(self):
        from django.core import mail

        for _ in range(3):
            self.client.post(self.url, {'email': 't@example.com'})
        self.assertEqual(len(mail.outbox), 3)

        response = self.client.post(self.url, {'email': 't@example.com'})
        # همان پاسخ همیشگی، اما ایمیل دیگری ارسال نمی‌شود.
        self.assertRedirects(response, reverse('account:password_reset_done'))
        self.assertEqual(len(mail.outbox), 3)


@override_settings(PUBLIC_WRITE_RATE_LIMITS={
    'comment': (10, 40), 'contact': (5, 20), 'register': (2, 10),
    'service_request': (5, 20), 'newsletter': (10, 40),
})
class RegistrationThrottleTests(TestCase):
    """ثبت‌نام عمومی هم مثل بقیهٔ POSTهای ناشناس سقف دارد."""

    def setUp(self):
        cache.clear()
        self.url = reverse('account:register')
        self.data = {
            'first_name': 'تست', 'last_name': 'کاربر',
            'username': 'bulk-user', 'email': 'bulk@example.com',
            'password': 'Strong-pass-123!', 'agree': 'on',
        }

    def test_third_attempt_is_rejected_with_429(self):
        first = self.client.post(self.url, self.data)
        self.assertEqual(first.status_code, 302)  # حساب ساخته شد
        second = self.client.post(self.url, self.data)
        self.assertEqual(second.status_code, 200)  # خطای تکراری‌بودن، هنوز سقف نرسیده
        third = self.client.post(self.url, self.data)
        self.assertEqual(third.status_code, 429)
        self.assertContains(third, 'تعداد تلاش‌های ثبت‌نام زیاد است', status_code=429)
        self.assertEqual(User.objects.filter(username='bulk-user').count(), 1)

    def test_other_usernames_have_their_own_budget(self):
        self.client.post(self.url, self.data)
        self.client.post(self.url, self.data)
        other = dict(self.data, username='other-user', email='other@example.com')
        response = self.client.post(self.url, other)
        self.assertEqual(response.status_code, 302)


class CardNumberStorageTests(TestCase):
    """شمارهٔ کامل کارت هرگز نباید در دیتابیس بنشیند؛ فقط ۴ رقم آخر."""

    def setUp(self):
        self.user = User.objects.create_user('card-user', password='Safe-pass-123!')
        self.profile = self.user.profile

    def _form(self, card):
        from dashboard.forms import ProfileEditForm

        return ProfileEditForm(
            data={'first_name': 'الف', 'last_name': 'ب', 'email': 'c@example.com',
                  'about_me': '', 'phone': '', 'card_number': card},
            instance=self.profile,
        )

    def test_full_card_is_reduced_to_last_four(self):
        form = self._form('6037498514785236')
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.card_number, '5236')
        self.assertEqual(self.profile.masked_card_number, '**** **** **** 5236')

    def test_prefilled_last_four_is_kept_not_rejected(self):
        self.profile.card_number = '5236'
        self.profile.save(update_fields=['card_number'])
        form = self._form('5236')
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.card_number, '5236')

    def test_partial_card_is_rejected(self):
        form = self._form('123456')
        self.assertFalse(form.is_valid())
