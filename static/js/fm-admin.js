/* ═══════════════════════════════════════════════════════════════════════
   ادمین جنگو — بهبود جدول‌های داده (فهرست‌های تغییر)
   ── سلول‌های «وضعیت» را به برچسب‌های رنگی قرصی‌شکلِ هم‌سبک با داشبورد
      کاربر تبدیل می‌کند (بدون تغییر سمت سرور تا خروجی CSV و list_editable
      دست‌نخورده بمانند). اگر متنی ناشناخته دید، همان متن خام می‌ماند.
   ═══════════════════════════════════════════════════════════════════════ */
(function () {
    'use strict';

    /* نگاشتِ متنِ نمایش‌داده‌شدهٔ وضعیت ← (کلاس برچسب، آیکون Font Awesome) */
    var STATUS_BADGES = {
        /* cart.Order */
        'در انتظار پرداخت': ['badge-pending', 'fa-clock'],
        'پرداخت شده - آماده دانلود': ['badge-paid', 'fa-check-circle'],
        'در حال پردازش': ['badge-processing', 'fa-cog fa-spin'],
        'ارسال شده': ['badge-shipped', 'fa-truck'],
        'تحویل داده شده': ['badge-delivered', 'fa-check-square'],
        /* payments.PaymentTransaction */
        'ایجاد شده': ['badge-created', 'fa-plus-circle'],
        'ارسال به درگاه': ['badge-redirected', 'fa-external-link'],
        'موفق': ['badge-paid', 'fa-check-circle'],
        'ناموفق': ['badge-failed', 'fa-times-circle'],
        /* services.ServiceRequest */
        'جدید': ['badge-new', 'fa-bell'],
        'تماس گرفته شد': ['badge-contacted', 'fa-phone'],
        'در حال بررسی': ['badge-in_progress', 'fa-cog fa-spin'],
        'پایان یافته': ['badge-done', 'fa-check-circle'],
        /* مشترکِ سفارش و خدمات */
        'لغو شده': ['badge-cancelled', 'fa-times-circle'],
        /* وضعیت محتوا: وبلاگ، محصول، بنر، دیدگاه */
        'پیش نویس شود': ['badge-draft', 'fa-edit'],
        'پیش نویس': ['badge-draft', 'fa-edit'],
        'منتشر شود': ['badge-published', 'fa-globe']
    };

    function decorateStatusCells() {
        var cells = document.querySelectorAll('#result_list td.field-status');
        cells.forEach(function (cell) {
            /* سلول‌های list_editable فرم ورودی دارند؛ دست نمی‌زنیم */
            if (cell.querySelector('input, select, textarea, button')) {
                return;
            }
            var text = (cell.textContent || '').replace(/\s+/g, ' ').trim();
            var entry = STATUS_BADGES[text];
            if (!entry) {
                return;
            }
            var badge = document.createElement('span');
            badge.className = 'badge ' + entry[0];
            badge.innerHTML = '<i class="fa ' + entry[1] + '" aria-hidden="true"></i> ';
            while (cell.firstChild) {
                badge.appendChild(cell.firstChild);
            }
            cell.appendChild(badge);
            cell.classList.add('field-status-badge');
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', decorateStatusCells);
    } else {
        decorateStatusCells();
    }
})();
