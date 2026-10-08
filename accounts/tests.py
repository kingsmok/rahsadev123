from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse


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
