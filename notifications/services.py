"""ثبت اعلان مدیریت و ارسال ایمیل/پیامک مربوط به آن."""
import logging
import threading

from django.conf import settings
from django.core.mail import send_mail
from django.db import close_old_connections, transaction
from django.urls import NoReverseMatch, reverse

from .models import AdminNotification, EmailSettings, SmsSettings

logger = logging.getLogger(__name__)

# نوع اعلان ← نام فیلد «ارسال شود؟» در تنظیمات ایمیل/پیامک
_CHANNEL_FLAGS = {
    'order_paid': 'notify_order_paid',
    'service_request': 'notify_service_request',
    'consultation': 'notify_service_request',
    'contact': 'notify_contact',
    'comment': 'notify_comment',
    'payment_problem': 'notify_order_paid',
}


def admin_change_url(obj):
    meta = obj._meta
    try:
        return reverse(f'admin:{meta.app_label}_{meta.model_name}_change', args=[obj.pk])
    except NoReverseMatch:
        return ''


def absolute_url(path):
    base = (getattr(settings, 'SITE_URL', '') or '').rstrip('/')
    if not path or not base or path.startswith('http'):
        return path
    return base + path


def notify(kind, title, message='', url='', level='info', dedupe_key=''):
    """Record an admin notification and deliver e-mail/SMS after commit.

    Never raises: a broken SMTP server or SMS panel must not break the checkout
    or the form that triggered the notification.
    """
    try:
        if dedupe_key and AdminNotification.objects.filter(dedupe_key=dedupe_key).exists():
            return None
        notification = AdminNotification.objects.create(
            kind=kind, level=level, title=title[:200], message=message, url=url[:500],
            dedupe_key=dedupe_key[:120],
        )
    except Exception:
        logger.exception('ثبت اعلان مدیریت انجام نشد (%s).', kind)
        return None
    transaction.on_commit(lambda: _schedule_delivery(notification.pk))
    return notification


def _schedule_delivery(pk):
    if getattr(settings, 'NOTIFICATIONS_ASYNC', True):
        threading.Thread(target=_deliver_in_thread, args=(pk,), daemon=True).start()
    else:
        deliver(pk)


def _deliver_in_thread(pk):
    try:
        deliver(pk)
    finally:
        close_old_connections()


def deliver(pk):
    notification = AdminNotification.objects.filter(pk=pk).first()
    if notification is None:
        return
    flag = _CHANNEL_FLAGS.get(notification.kind)
    if not flag:
        return
    updates = []
    if _send_email(notification, flag):
        notification.emailed = True
        updates.append('emailed')
    if _send_sms(notification, flag):
        notification.sms_sent = True
        updates.append('sms_sent')
    if updates:
        notification.save(update_fields=updates)


def _site_name():
    try:
        from core.branding import get_brand

        return get_brand().name
    except Exception:
        return 'فروشگاه'


def _send_email(notification, flag):
    try:
        config = EmailSettings.load()
        recipients = config.recipient_list()
        if not recipients or not getattr(config, flag, False):
            return False
        link = absolute_url(notification.url)
        body = '\n\n'.join(part for part in (
            notification.title,
            notification.message,
            f'بررسی در پنل مدیریت: {link}' if link else '',
        ) if part)
        send_mail(f'[{_site_name()}] {notification.title}', body, None, recipients, fail_silently=False)
        return True
    except Exception:
        logger.exception('ارسال ایمیل اعلان %s انجام نشد.', notification.pk)
        return False


def _send_sms(notification, flag):
    from .sms import SmsError, SmsIrClient

    try:
        config = SmsSettings.load()
        mobiles = config.admin_mobile_list()
        if not (config.is_usable and mobiles and getattr(config, flag, False)):
            return False
        client = SmsIrClient(config.api_key)
        detail = (notification.message or '').replace('\n', ' ')
        if config.alert_template_id:
            for mobile in mobiles:
                client.send_verify(mobile, config.alert_template_id, {
                    'TITLE': notification.get_kind_display(),
                    'DETAIL': detail[:25] or notification.title[:25],
                })
        elif config.line_number:
            text = f'{_site_name()}: {notification.title}'
            if detail:
                text += f'\n{detail[:120]}'
            client.send_bulk(config.line_number, text, mobiles)
        else:
            return False
        return True
    except SmsError as exc:
        logger.warning('ارسال پیامک اعلان %s انجام نشد: %s', notification.pk, exc)
        return False
    except Exception:
        logger.exception('ارسال پیامک اعلان %s انجام نشد.', notification.pk)
        return False


def send_customer_order_sms(order):
    """پیامک «خرید موفق» به مشتری، اگر قالب آن در تنظیمات پیامک تعیین شده باشد."""
    from .sms import SmsError, SmsIrClient, normalize_mobile

    try:
        config = SmsSettings.load()
        if not (config.is_usable and config.customer_order_template_id):
            return False
        profile = getattr(order.user, 'profile', None)
        mobile = normalize_mobile(getattr(profile, 'phone', '') or '')
        if not mobile:
            return False
        SmsIrClient(config.api_key).send_verify(mobile, config.customer_order_template_id, {
            'ORDER': order.order_number,
            'AMOUNT': f'{order.final_price:,}',
        })
        return True
    except SmsError as exc:
        logger.warning('پیامک خرید سفارش %s ارسال نشد: %s', order.pk, exc)
    except Exception:
        logger.exception('پیامک خرید سفارش %s ارسال نشد.', order.pk)
    return False
