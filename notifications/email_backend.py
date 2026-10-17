"""Backend ایمیلی که تنظیمات SMTP را از «تنظیمات ایمیل (SMTP)» پنل مدیریت می‌خواند.

اگر آن تنظیمات فعال نباشد، backend تعیین‌شده در محیط
(``settings.EMAIL_FALLBACK_BACKEND`` — همان مقدار قبلی ``EMAIL_BACKEND``) استفاده
می‌شود؛ بنابراین نصب‌های فعلی بدون تغییر کار می‌کنند.
"""
import logging

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend
from django.core.mail.backends.smtp import EmailBackend as SmtpEmailBackend
from django.db import DatabaseError
from django.utils.module_loading import import_string

logger = logging.getLogger(__name__)


def smtp_backend_from_settings(config, fail_silently=False):
    return SmtpEmailBackend(
        host=config.host,
        port=config.port,
        username=config.username or '',
        password=config.password or '',
        use_tls=config.security == 'tls',
        use_ssl=config.security == 'ssl',
        timeout=config.timeout,
        fail_silently=fail_silently,
    )


class ConfigurableEmailBackend(BaseEmailBackend):
    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently)
        self._kwargs = kwargs
        self._backend = None
        self._sender = ''

    def _resolve(self):
        if self._backend is not None:
            return self._backend
        config = None
        try:
            from .models import EmailSettings

            config = EmailSettings.load()
        except DatabaseError:
            # Tables not migrated yet (first deploy): fall back silently.
            config = None
        if config is not None and config.is_usable:
            self._sender = config.sender
            self._backend = smtp_backend_from_settings(config, fail_silently=self.fail_silently)
        else:
            backend_path = getattr(settings, 'EMAIL_FALLBACK_BACKEND',
                                   'django.core.mail.backends.console.EmailBackend')
            if backend_path.endswith('ConfigurableEmailBackend'):
                backend_path = 'django.core.mail.backends.console.EmailBackend'
            self._backend = import_string(backend_path)(fail_silently=self.fail_silently, **self._kwargs)
        return self._backend

    def open(self):
        return self._resolve().open()

    def close(self):
        if self._backend is not None:
            self._backend.close()

    def send_messages(self, email_messages):
        backend = self._resolve()
        if self._sender:
            default_sender = getattr(settings, 'DEFAULT_FROM_EMAIL', '')
            for message in email_messages:
                if not message.from_email or message.from_email == default_sender:
                    message.from_email = self._sender
        return backend.send_messages(email_messages)
