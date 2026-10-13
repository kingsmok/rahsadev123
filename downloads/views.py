import os

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import F
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect

from .models import DownloadToken


# Statuses meaning the money went back to the customer.  A token whose order is
# in one of these must stop serving the file: otherwise buying a product,
# downloading it, and asking for a refund within the return window keeps both
# the file and the money.  This mirrors the entitlement check on the product
# page (product.views._has_purchased_product), so the shop and the download
# link never disagree about whether the customer still owns the file.
REVOKED_ORDER_STATUSES = frozenset({'cancelled', 'refunded'})


@login_required
def download_file(request, token):
    download_token = get_object_or_404(DownloadToken, token=token, user=request.user)

    if download_token.order.status in REVOKED_ORDER_STATUSES:
        messages.error(request, 'این سفارش لغو یا مسترد شده و امکان دانلود فایل آن وجود ندارد.')
        return redirect('dashboard:order_detail', order_number=download_token.order.order_number)

    if not download_token.is_valid:
        messages.error(request, 'این لینک دانلود منقضی شده یا به سقف تعداد دانلود رسیده است.')
        return redirect('dashboard:order_detail', order_number=download_token.order.order_number)

    digital_asset = getattr(download_token.product, 'digital_asset', None)
    if not digital_asset or not digital_asset.file:
        raise Http404('فایل دیجیتال یافت نشد.')

    # Consume the token before opening the file.  ``register_download`` is an
    # atomic conditional update, so two tabs cannot both receive a sixth file
    # when the token has one download left.
    if not download_token.register_download():
        messages.error(request, 'این لینک دانلود منقضی شده یا به سقف تعداد دانلود رسیده است.')
        return redirect('dashboard:order_detail', order_number=download_token.order.order_number)

    type(digital_asset).objects.filter(pk=digital_asset.pk).update(
        download_count=F('download_count') + 1
    )

    file_path = digital_asset.file.path
    file_name = os.path.basename(file_path)
    return FileResponse(open(file_path, 'rb'), as_attachment=True, filename=file_name)
