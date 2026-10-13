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
