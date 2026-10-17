import logging
import os

from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.db.models import F
from django.http import FileResponse, Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.cache import never_cache

from .models import REVOKED_ORDER_STATUSES, DownloadToken

logger = logging.getLogger(__name__)


def _report_missing_file(asset, download_token):
    """A paid file that cannot be delivered must reach the shop owner, not just a log."""
    logger.error('فایل دیجیتال محصول «%s» (DigitalAsset#%s) قابل تحویل نیست.', asset.product.title, asset.pk)
    try:
        from notifications.services import admin_change_url, notify

        notify(
            'system',
            f'فایل محصول «{asset.product.title}» قابل دانلود نیست',
            message=(f'خریدار سفارش {download_token.order.order_number} نتوانست فایل را دریافت کند. '
                     'فایل محصول را دوباره آپلود کنید یا لینک دانلود آن را بررسی کنید.'),
            url=admin_change_url(asset.product),
            level='danger',
            dedupe_key=f'missing-digital-file:{asset.pk}:{asset.file.name if asset.file else asset.external_url}'[:120],
        )
    except Exception:  # the customer still gets a clear message below
        logger.exception('اعلان فایل ناموجود ثبت نشد.')


@never_cache
def download_file(request, token):
    """Serve a purchased file.

    An account's token works only for that account (anonymous visitors are sent
    to the login page, other accounts get a 404 — as before).  A guest order's
    token additionally needs access to that order: the browser session that
    bought it or opened its secret link.  The token alone is never enough.
    """
    from cart.guest import can_access_order

    download_token = get_object_or_404(DownloadToken.objects.select_related('order', 'product'), token=token)
    order = download_token.order
    if download_token.user_id:
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if request.user.pk != download_token.user_id:
            raise Http404('فایل یافت نشد.')
        order_page = reverse('dashboard:order_detail', kwargs={'order_number': order.order_number})
    else:
        if not can_access_order(request, order) or not order.access_token:
            messages.info(request, 'برای دانلود، صفحهٔ سفارش را از لینکی که پس از خرید دریافت کردید باز کنید '
                                   'یا سفارش را با شمارهٔ سفارش و موبایل پیگیری کنید.')
            return redirect('cart:track_order')
        order_page = reverse('cart:guest_order', kwargs={'access_token': order.access_token})

    if download_token.order.status in REVOKED_ORDER_STATUSES:
        messages.error(request, 'این سفارش لغو یا مسترد شده و امکان دانلود فایل آن وجود ندارد.')
        return redirect(order_page)

    if not download_token.is_valid:
        messages.error(request, 'این لینک دانلود منقضی شده یا به سقف تعداد دانلود رسیده است.')
        return redirect(order_page)

    digital_asset = getattr(download_token.product, 'digital_asset', None)
    if digital_asset is None:
        raise Http404('فایل دیجیتال یافت نشد.')

    # Check the file *before* consuming a download: a missing upload used to
    # crash with a server error after one of the buyer's downloads was spent.
    if not digital_asset.is_deliverable():
        _report_missing_file(digital_asset, download_token)
        messages.error(request, 'فایل این محصول موقتاً در دسترس نیست. مدیر فروشگاه مطلع شد؛ '
                                'به‌زودی می‌توانید دوباره دانلود کنید (از تعداد دانلود شما کم نشد).')
        return redirect(order_page)

    # Consume the token before handing out the file.  ``register_download`` is
    # an atomic conditional update, so two tabs cannot both receive a sixth file
    # when the token has one download left.
    if not download_token.register_download():
        messages.error(request, 'این لینک دانلود منقضی شده یا به سقف تعداد دانلود رسیده است.')
        return redirect(order_page)

    type(digital_asset).objects.filter(pk=digital_asset.pk).update(
        download_count=F('download_count') + 1
    )

    if digital_asset.is_link:
        # The link is only revealed here, after every entitlement check.
        response = HttpResponseRedirect(digital_asset.external_url)
        response['Cache-Control'] = 'no-store'
        response['Referrer-Policy'] = 'no-referrer'
        return response

    file_path = digital_asset.file.path
    file_name = os.path.basename(file_path)
    return FileResponse(open(file_path, 'rb'), as_attachment=True, filename=file_name)
