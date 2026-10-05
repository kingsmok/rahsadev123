import os

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect

from .models import DownloadToken


@login_required
def download_file(request, token):
    download_token = get_object_or_404(DownloadToken, token=token, user=request.user)

    if not download_token.is_valid:
        messages.error(request, 'این لینک دانلود منقضی شده یا به سقف تعداد دانلود رسیده است.')
        return redirect('dashboard:order_detail', order_number=download_token.order.order_number)

    digital_asset = getattr(download_token.product, 'digital_asset', None)
    if not digital_asset or not digital_asset.file:
        raise Http404('فایل دیجیتال یافت نشد.')

    download_token.register_download()
    digital_asset.download_count = digital_asset.download_count + 1
    digital_asset.save(update_fields=['download_count'])

    file_path = digital_asset.file.path
    file_name = os.path.basename(file_path)
    return FileResponse(open(file_path, 'rb'), as_attachment=True, filename=file_name)
