"""ساخت کاربر مدیر پیش‌فرض برای اجرای سریع پروژه.

    python manage.py create_default_admin
    python manage.py create_default_admin --username reza --password My-Long-Pass-123

این دستور «آیدمپوتنت» است: اگر کاربر وجود داشته باشد رمز او تغییر نمی‌کند
(مگر با --reset-password). در محیط عملیاتی ساخت حساب با رمز پیش‌فرض عمومی
مجاز نیست تا حساب admin/admin1234 روی سرور واقعی ساخته نشود.
"""
import os

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

DEFAULT_USERNAME = 'admin'
DEFAULT_PASSWORD = 'admin1234'
MIN_PASSWORD_LENGTH = 8


class Command(BaseCommand):
    help = 'ساخت (یا به‌روزرسانی) کاربر مدیر پیش‌فرض برای ورود به /admin/ و /admin-panel/'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            default=os.environ.get('ADMIN_DEFAULT_USERNAME', DEFAULT_USERNAME),
            help=f'نام کاربری مدیر (پیش‌فرض: {DEFAULT_USERNAME} یا متغیر ADMIN_DEFAULT_USERNAME)',
        )
        parser.add_argument(
            '--password',
            default=os.environ.get('ADMIN_DEFAULT_PASSWORD', DEFAULT_PASSWORD),
            help='رمز عبور مدیر (پیش‌فرض: admin1234 یا متغیر ADMIN_DEFAULT_PASSWORD)',
        )
        parser.add_argument(
            '--email',
            default=os.environ.get('ADMIN_DEFAULT_EMAIL', 'admin@example.test'),
            help='ایمیل مدیر',
        )
        parser.add_argument(
            '--reset-password',
            action='store_true',
            help='رمز کاربر موجود را هم به مقدار داده‌شده تغییر بده',
        )

    def handle(self, *args, **options):
        username = (options['username'] or '').strip()
        password = options['password'] or ''
        email = (options['email'] or '').strip()

        if not username:
            raise CommandError('نام کاربری نمی‌تواند خالی باشد.')
        if len(password) < MIN_PASSWORD_LENGTH:
            raise CommandError(
                f'رمز عبور باید حداقل {MIN_PASSWORD_LENGTH} کاراکتر باشد.'
            )
        if not settings.DEBUG and password == DEFAULT_PASSWORD:
            raise CommandError(
                'در محیط عملیاتی (DEBUG=False) نمی‌توان از رمز پیش‌فرض admin1234 استفاده کرد. '
                'رمز قوی را با --password یا متغیر ADMIN_DEFAULT_PASSWORD بدهید.'
            )

        user_model = get_user_model()
        user = user_model.objects.filter(username=username).first()
        password_applied = True

        if user is None:
            user = user_model.objects.create_superuser(
                username=username, email=email, password=password
            )
            self.stdout.write(self.style.SUCCESS(
                f'کاربر مدیر «{username}» ساخته شد.'
            ))
        else:
            user.is_staff = True
            user.is_superuser = True
            user.is_active = True
            if email and not user.email:
                user.email = email
            if options['reset_password']:
                user.set_password(password)
                self.stdout.write(self.style.SUCCESS(
                    f'رمز کاربر «{username}» بازنشانی شد.'
                ))
            else:
                # رمز کاربر موجود بدون درخواست صریح تغییر نمی‌کند، پس مقدار
                # داده‌شده در خلاصهٔ پایین هم به‌عنوان رمز معتبر چاپ نمی‌شود.
                password_applied = False
                self.stdout.write(
                    f'کاربر «{username}» از قبل وجود داشت؛ رمز او تغییر نکرد.'
                )
            user.save()

        self.stdout.write('')
        self.stdout.write('════════ اطلاعات ورود ════════')
        self.stdout.write(f'  نام کاربری : {username}')
        if password_applied:
            self.stdout.write(f'  رمز عبور   : {password}')
        else:
            self.stdout.write('  رمز عبور   : (تغییر نکرد — رمز قبلی معتبر است)')
        self.stdout.write('  پنل تحلیل  : /admin-panel/')
        self.stdout.write('  ادمین جنگو : /admin/')
        if password_applied and password == DEFAULT_PASSWORD:
            self.stdout.write(self.style.WARNING(
                '  ⚠ رمز پیش‌فرض فقط برای توسعه است؛ پیش از دیپلوی آن را عوض کنید.'
            ))
        self.stdout.write('══════════════════════════════')
