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

/* ═══════════════════════════════════════════════════════════════════════
   کشوهای ادمین در موبایل (زیر ۷۶۸px)
   ── ۱) منوی همبرگری: جنگو در این عرض سایدبار بخش‌ها را پنهان می‌کند؛ کشوی
      admin/includes/mobile_drawer.html دسترسی سریع و همهٔ بخش‌ها را دارد.
   ── ۲) فیلترهای فهرست‌ها (#changelist-filter): در موبایل زیر جدول و گاهی
      ۱۶۰۰px پایین‌تر بود؛ حالا دکمهٔ «فیلترها» بالای فهرست بازش می‌کند.
   رفتار مثل منوی همبرگری فروشگاه: پس‌زمینهٔ تیره، Esc، کشیدن انگشت به راست،
   نگه‌داشتن فوکوس داخل کشو، قفل اسکرول صفحه و برگرداندن فوکوس به دکمه.
   ═══════════════════════════════════════════════════════════════════════ */
(function () {
    'use strict';

    var root = document.documentElement;
    var query = window.matchMedia ? window.matchMedia('(max-width: 767px)') : null;
    var FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), summary, [tabindex]:not([tabindex="-1"])';
    var backdrop = null;
    var current = null;     // کشوی باز
    var hideTimer = null;

    function drawerMode() { return !query || query.matches; }
    function visible(element) {
        return !!element && element.getClientRects().length > 0 && window.getComputedStyle(element).visibility !== 'hidden';
    }

    function createDrawer(panel, trigger, closeButton) {
        var lastTrigger = null;
        var api = {panel: panel, trigger: trigger};

        function isOpen() { return current === api; }

        api.open = function () {
            if (isOpen() || !drawerMode()) return;
            if (current) current.close({restoreFocus: false});
            window.clearTimeout(hideTimer);
            lastTrigger = document.activeElement && document.activeElement !== document.body ? document.activeElement : trigger;
            current = api;
            backdrop.hidden = false;
            void panel.offsetWidth;   // حالت بسته رسم شود تا انیمیشن ورود دیده شود
            panel.classList.add('is-open');
            backdrop.classList.add('is-visible');
            root.classList.add('fm-adm-nav-open');
            panel.setAttribute('role', 'dialog');
            panel.setAttribute('aria-modal', 'true');
            trigger.setAttribute('aria-expanded', 'true');
            window.setTimeout(function () { if (isOpen() && closeButton) closeButton.focus(); }, 40);
        };

        api.close = function (options) {
            options = options || {};
            if (!isOpen()) return;
            current = null;
            panel.classList.remove('is-open');
            backdrop.classList.remove('is-visible');
            root.classList.remove('fm-adm-nav-open');
            panel.removeAttribute('role');
            panel.removeAttribute('aria-modal');
            panel.style.removeProperty('transform');
            panel.style.removeProperty('transition');
            backdrop.style.removeProperty('opacity');
            trigger.setAttribute('aria-expanded', 'false');
            hideTimer = window.setTimeout(function () { if (!current) backdrop.hidden = true; }, 320);
            if (options.restoreFocus !== false && visible(lastTrigger) && document.contains(lastTrigger)) lastTrigger.focus();
        };

        api.focusables = function () {
            return Array.prototype.filter.call(panel.querySelectorAll(FOCUSABLE), visible);
        };

        trigger.addEventListener('click', function () {
            if (isOpen()) api.close();
            else api.open();
        });
        panel.addEventListener('click', function (event) {
            if (!isOpen()) return;
            if (event.target.closest('[data-fm-adm-close]')) {
                api.close();
            } else if (event.target.closest('a[href]')) {
                api.close({restoreFocus: false});
            }
        });
        enableSwipe(api);
        return api;
    }

    function trapFocus(event) {
        var items = current.focusables();
        if (!items.length) return;
        var first = items[0];
        var last = items[items.length - 1];
        if (!current.panel.contains(document.activeElement)) {
            event.preventDefault();
            (event.shiftKey ? last : first).focus();
        } else if (event.shiftKey && document.activeElement === first) {
            event.preventDefault();
            last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
            event.preventDefault();
            first.focus();
        }
    }

    function enableSwipe(api) {
        var panel = api.panel;
        var swipe = null;
        panel.addEventListener('touchstart', function (event) {
            if (current !== api || event.touches.length !== 1 || event.target.closest('input, select, textarea')) return;
            swipe = {x: event.touches[0].clientX, y: event.touches[0].clientY, time: Date.now(), distance: 0, mode: null,
                     width: panel.getBoundingClientRect().width || 1};
        }, {passive: true});
        panel.addEventListener('touchmove', function (event) {
            if (!swipe) return;
            var dx = event.touches[0].clientX - swipe.x;   // کشو سمت راست است: کشیدن به راست می‌بندد
            var dy = event.touches[0].clientY - swipe.y;
            if (!swipe.mode) {
                if (Math.abs(dx) < 10 && Math.abs(dy) < 10) return;
                swipe.mode = dx > 0 && Math.abs(dx) > Math.abs(dy) * 1.3 ? 'swipe' : 'scroll';
                if (swipe.mode === 'swipe') panel.style.setProperty('transition', 'none', 'important');
            }
            if (swipe.mode !== 'swipe') return;
            swipe.distance = Math.max(0, dx);
            panel.style.setProperty('transform', 'translateX(' + swipe.distance + 'px)', 'important');
            backdrop.style.opacity = String(Math.max(0, 1 - swipe.distance / swipe.width));
        }, {passive: true});
        function end() {
            if (!swipe) return;
            var gesture = swipe;
            swipe = null;
            if (gesture.mode !== 'swipe') return;
            panel.style.removeProperty('transition');
            panel.style.removeProperty('transform');
            backdrop.style.removeProperty('opacity');
            if (gesture.distance > gesture.width * 0.3 || (gesture.distance > 40 && Date.now() - gesture.time < 300)) {
                api.close({restoreFocus: false});
            }
        }
        panel.addEventListener('touchend', end, {passive: true});
        panel.addEventListener('touchcancel', end, {passive: true});
    }

    /* دکمه و سربرگ کشوی فیلتر فهرست‌ها؛ قالب جنگو دست‌نخورده می‌ماند. */
    function setUpChangelistFilter() {
        var filter = document.getElementById('changelist-filter');
        var container = document.querySelector('#changelist .changelist-form-container');
        if (!filter || !container) return;
        var active = !!filter.querySelector('#changelist-filter-extra-actions a[href]:not(.hidelink):not(.viewlink)');
        var toggle = document.createElement('button');
        toggle.type = 'button';
        toggle.className = 'fm-adm-filter-toggle';
        toggle.setAttribute('aria-controls', 'changelist-filter');
        toggle.setAttribute('aria-expanded', 'false');
        toggle.setAttribute('aria-haspopup', 'dialog');
        toggle.innerHTML = '<i class="fa-solid fa-filter" aria-hidden="true"></i><span>فیلترها</span>' +
            (active ? '<span class="fm-adm-filter-toggle__on">فعال</span>' : '');
        container.insertBefore(toggle, container.firstChild);
        var close = document.createElement('button');
        close.type = 'button';
        close.className = 'fm-adm-filter-close';
        close.setAttribute('data-fm-adm-close', '');
        close.setAttribute('aria-label', 'بستن فیلترها');
        close.innerHTML = '<i class="fa-solid fa-xmark" aria-hidden="true"></i>';
        filter.insertBefore(close, filter.firstChild);
        createDrawer(filter, toggle, close);
    }

    function init() {
        backdrop = document.createElement('div');
        backdrop.className = 'fm-adm-backdrop';
        backdrop.hidden = true;
        backdrop.setAttribute('aria-hidden', 'true');
        document.body.appendChild(backdrop);
        backdrop.addEventListener('click', function () { if (current) current.close(); });

        var menu = document.querySelector('[data-fm-adm-drawer]');
        var menuTrigger = document.querySelector('[data-fm-adm-open]');
        if (menu && menuTrigger) {
            // سربرگ چسبان لایهٔ z-index خودش را دارد؛ کشو در <body> روی همه‌چیز می‌نشیند.
            document.body.appendChild(menu);
            createDrawer(menu, menuTrigger, menu.querySelector('[data-fm-adm-close]'));
        }
        setUpChangelistFilter();

        document.addEventListener('keydown', function (event) {
            if (!current) return;
            if (event.key === 'Escape') {
                event.preventDefault();
                current.close();
            } else if (event.key === 'Tab') {
                trapFocus(event);
            }
        });
        if (query) {
            var onChange = function () { if (!query.matches && current) current.close({restoreFocus: false}); };
            if (query.addEventListener) query.addEventListener('change', onChange);
            else if (query.addListener) query.addListener(onChange);
        }
        window.addEventListener('pageshow', function (event) {
            if (event.persisted && current) current.close({restoreFocus: false});
        });
    }

    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
})();
