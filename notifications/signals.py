"""رویدادهایی که برای مدیر اعلان می‌سازند.

سفارش پرداخت‌شده، درخواست طراحی سایت/مشاوره، پیام تماس با ما، دیدگاه در
انتظار تأیید و ثبت‌نام کاربر. ارسال ایمیل/پیامک بعد از commit و در پس‌زمینه
انجام می‌شود (``services.notify``).
"""
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from cart.models import Order
from core.models import ContactUs
from product.models import ProductComment
from services.models import ServiceRequest

from .services import admin_change_url, notify, send_customer_order_sms


@receiver(pre_save, sender=Order, dispatch_uid='notifications_order_status_before')
def _remember_order_status(sender, instance, **kwargs):
    if instance.pk:
        instance._fm_previous_status = (
            Order.objects.filter(pk=instance.pk).values_list('status', flat=True).first()
        )
    else:
        instance._fm_previous_status = None


@receiver(post_save, sender=Order, dispatch_uid='notifications_order_paid')
def _order_paid(sender, instance, created, raw=False, **kwargs):
    if raw or instance.status != 'paid' or getattr(instance, '_fm_previous_status', None) == 'paid':
        return
    user = instance.user
    if user:
        customer = user.get_full_name() or user.get_username()
    else:
        customer = f'مهمان ({instance.contact_mobile or instance.contact_email or "بدون اطلاعات تماس"})'
    notify(
        'order_paid',
        f'سفارش {instance.order_number} پرداخت شد',
        f'مشتری: {customer} — مبلغ: {instance.final_price:,} تومان',
        url=admin_change_url(instance),
        level='success',
        dedupe_key=f'order_paid:{instance.pk}',
    )
    order_pk = instance.pk
    transaction.on_commit(lambda: _customer_sms(order_pk))


def _customer_sms(order_pk):
    order = Order.objects.select_related('user').filter(pk=order_pk).first()
    if order is not None:
        send_customer_order_sms(order)


@receiver(post_save, sender=ServiceRequest, dispatch_uid='notifications_service_request')
def _service_request(sender, instance, created, raw=False, **kwargs):
    if raw or not created:
        return
    is_consultation = not (instance.package_id or instance.project_type)
    subject = instance.project_type or (instance.package.title if instance.package_id else '')
    notify(
        'consultation' if is_consultation else 'service_request',
        ('درخواست مشاوره جدید' if is_consultation else 'درخواست طراحی سایت جدید') + f' از {instance.full_name}',
        '\n'.join(part for part in (
            f'تلفن: {instance.phone}',
            f'موضوع: {subject}' if subject else '',
            f'بودجه: {instance.budget}' if instance.budget else '',
            (instance.message or '')[:300],
        ) if part),
        url=admin_change_url(instance),
        level='warning',
        dedupe_key=f'service_request:{instance.pk}',
    )


@receiver(post_save, sender=ContactUs, dispatch_uid='notifications_contact')
def _contact(sender, instance, created, raw=False, **kwargs):
    if raw or not created:
        return
    notify(
        'contact',
        f'پیام جدید از {instance.first_name} {instance.last_name}'.strip(),
        f'تلفن: {instance.phone}\n{(instance.message or "")[:300]}',
        url=admin_change_url(instance),
        level='info',
        dedupe_key=f'contact:{instance.pk}',
    )


@receiver(post_save, sender=ProductComment, dispatch_uid='notifications_comment')
def _comment(sender, instance, created, raw=False, **kwargs):
    if raw or not created or instance.status != 'pending':
        return
    notify(
        'comment',
        f'دیدگاه جدید برای «{instance.product.title[:80]}» در انتظار تأیید',
        f'{instance.author.get_username()}: {(instance.body or "")[:200]}',
        url=admin_change_url(instance),
        level='info',
        dedupe_key=f'comment:{instance.pk}',
    )


@receiver(post_save, sender=get_user_model(), dispatch_uid='notifications_user_registered')
def _user_registered(sender, instance, created, raw=False, **kwargs):
    if raw or not created or instance.is_staff:
        return
    notify(
        'user_registered',
        f'کاربر جدید: {instance.get_username()}',
        url=admin_change_url(instance),
        level='info',
        dedupe_key=f'user:{instance.pk}',
    )
