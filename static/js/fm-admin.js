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

/* زنگولهٔ اعلان‌های مدیریت: هر ۶۰ ثانیه تعداد خوانده‌نشده‌ها به‌روز می‌شود و
   برای اعلان تازه، عنوان تب هم تغییر می‌کند تا مدیر متوجه سفارش/درخواست جدید شود. */
(function () {
    'use strict';
    var bell = document.querySelector('[data-fm-bell]');
    if (!bell || !window.fetch) return;
    var url = bell.getAttribute('data-feed-url');
    var countNode = bell.querySelector('[data-fm-bell-count]');
    var list = bell.querySelector('[data-fm-bell-list]');
    var baseTitle = document.title;
    var lastSeen = null;

    function escapeHtml(value) {
        return String(value).replace(/[&<>"']/g, function (ch) {
            return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[ch];
        });
    }

    function render(data) {
        var unread = data.unread || 0;
        if (countNode) {
            countNode.textContent = unread > 99 ? '99+' : String(unread);
            countNode.hidden = unread <= 0;
        }
        document.title = unread > 0 ? '(' + unread + ') ' + baseTitle : baseTitle;
        if (list && Array.isArray(data.items) && !bell.open) {
            list.innerHTML = data.items.length ? data.items.map(function (item) {
                return '<li class="fm-bell__item fm-bell__item--' + escapeHtml(item.level) + (item.is_read ? '' : ' is-unread') + '">' +
                    '<a href="' + escapeHtml(item.open_url) + '"><i class="fa-solid ' + escapeHtml(item.icon) + '" aria-hidden="true"></i>' +
                    '<span class="fm-bell__text"><span class="fm-bell__title">' + escapeHtml(item.title) + '</span>' +
                    '<small>' + escapeHtml(item.kind) + ' · ' + escapeHtml(item.created) + '</small></span></a></li>';
            }).join('') : '<li class="fm-bell__empty">هنوز اعلانی ثبت نشده است.</li>';
        }
        if (lastSeen !== null && data.latest_id > lastSeen) {
            bell.classList.add('has-new');
            window.setTimeout(function () { bell.classList.remove('has-new'); }, 4000);
        }
        lastSeen = data.latest_id || 0;
    }

    function poll() {
        if (document.hidden) return;
        fetch(url, {credentials: 'same-origin', headers: {'X-Requested-With': 'XMLHttpRequest'}})
            .then(function (response) { return response.ok ? response.json() : null; })
            .then(function (data) { if (data) render(data); })
            .catch(function () {});
    }

    poll();
    window.setInterval(poll, 60000);
    document.addEventListener('visibilitychange', function () { if (!document.hidden) poll(); });
    document.addEventListener('click', function (event) {
        if (bell.open && !bell.contains(event.target)) bell.open = false;
    });
})();
