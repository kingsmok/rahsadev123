from django import template

from ..models import AdminNotification

register = template.Library()


@register.inclusion_tag('notifications/admin_bell.html', takes_context=True)
def admin_notification_bell(context):
    request = context.get('request')
    user = getattr(request, 'user', None)
    if not (user and user.is_active and user.is_staff and user.has_perm('notifications.view_adminnotification')):
        return {'show_bell': False}
    unread = AdminNotification.objects.filter(is_read=False)
    return {
        'show_bell': True,
        'unread_count': unread.count(),
        'latest': list(AdminNotification.objects.all()[:8]),
        'request': request,
    }
