from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.core.validators import RegexValidator


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, verbose_name='کاربر')
    first_name = models.CharField(max_length=100, null=True, blank=True, verbose_name='نام')
    last_name = models.CharField(max_length=100, null=True, blank=True, verbose_name='نام خانوادگی')
    email = models.EmailField(max_length=100, null=True, blank=True, verbose_name='ایمیل')
    about_me = models.CharField(max_length=250, null=True, blank=True, verbose_name='درباره من')
    phone = models.CharField(max_length=11, null=True, blank=True, validators=[RegexValidator(regex=r'^09\d{9}$', message='شماره تلفن باید با 09 شروع شده و 11 رقم باشد')], verbose_name='شماره تلفن')
    card_number = models.CharField(max_length=16, validators=[RegexValidator(regex=r'^\d{16}$', message='شماره کارت باید 16 رقم باشد', code='invalid_card_number')], null=True, blank=True, verbose_name='شماره کارت')
    image = models.ImageField(upload_to='profile/', null=True, blank=True, verbose_name='تصویر پروفایل')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ایجاد')

    class Meta:
        verbose_name = 'پروفایل'
        verbose_name_plural = 'پروفایل ها'

    @property
    def masked_card_number(self):
        """Safe representation for customer-facing pages and admin lists."""
        if not self.card_number:
            return ''
        visible = self.card_number[-4:]
        return f'**** **** **** {visible}'

    def __str__(self):
        return f"پروفایل {self.user.username}"


def ensure_user_profile(sender, instance, **kwargs):
    """Guarantee exactly one ``Profile`` row per user.

    The previous implementation created the profile only on insert and then
    unconditionally called ``instance.profile.save()`` on *every* subsequent
    save.  A user created outside this signal (``bulk_create``, a data
    migration, an imported database) has no profile, so that attribute access
    raised ``RelatedObjectDoesNotExist`` — and because Django updates
    ``last_login`` during authentication, such a user could not even log in.

    ``get_or_create`` repairs those rows on first access instead of crashing,
    and it also removes a redundant UPDATE-query on every user save.
    """
    Profile.objects.get_or_create(
        user=instance,
        defaults={
            'first_name': instance.first_name,
            'last_name': instance.last_name,
            'email': instance.email,
        },
    )


post_save.connect(ensure_user_profile, sender=User)

