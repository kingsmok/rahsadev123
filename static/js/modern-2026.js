/* ═══════════════════════════════════════════════════════════
   به‌روزرسانی ۲۰۲۶ — فایل‌مارکت
   حالت شب/روز + جست‌وجوی زنده + بازگشت به بالا + خبرنامه
   ═══════════════════════════════════════════════════════════ */
(function () {
    'use strict';

    /* ---------- ۱) حالت شب/روز ---------- */
    var themeMeta = document.querySelector('meta[name="theme-color"]');

    function applyTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        if (themeMeta) themeMeta.setAttribute('content', theme === 'dark' ? '#0f1720' : '#ffffff');
    }

    // مقدار اولیه در <head> ست شده (ضد فلش)؛ اینجا فقط همگام‌سازی
    var saved = null;
    try { saved = localStorage.getItem('fm-theme'); } catch (e) {}
    applyTheme(saved || (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'));

    document.addEventListener('click', function (e) {
        var btn = e.target.closest('.theme-toggle');
        if (!btn) return;
        e.preventDefault();
        var current = document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
        var next = current === 'dark' ? 'light' : 'dark';
        try { localStorage.setItem('fm-theme', next); } catch (err) {}
        applyTheme(next);
    });

    /* ---------- ۲) جست‌وجوی زنده (AJAX) ---------- */
    function faPrice(n) {
        try { return Number(n).toLocaleString('fa-IR'); } catch (e) { return n; }
    }

    function initLiveSearch(form) {
        var input = form.querySelector('input[type="text"]');
        if (!input) return;
        var wrap = form.parentElement;
        if (!wrap.classList.contains('live-search-wrap')) {
            wrap.classList.add('live-search-wrap');
        }
        // ساخت باکس نتایج
        var box = document.createElement('div');
        box.className = 'live-search-results';
        box.setAttribute('role', 'listbox');
        wrap.appendChild(box);

        var timer = null;
        var lastQuery = '';

        function hide() { box.classList.remove('open'); }
        function show() { box.classList.add('open'); }

        function render(items, query) {
            if (!items.length) {
                box.innerHTML = '<div class="ls-empty">نتیجه‌ای برای «' + escapeHtml(query) + '» پیدا نشد</div>' +
                    '<a class="ls-all" href="' + SEARCH_URL + encodeURIComponent(query) + '">مشاهده همه فایل‌ها</a>';
                return;
            }
            var html = items.map(function (p) {
                var img = p.image
                    ? '<img src="' + p.image + '" alt="' + escapeHtml(p.title) + '" loading="lazy">'
                    : '<img src="' + FALLBACK_IMG + '" alt="' + escapeHtml(p.title) + '" loading="lazy">';
                return '<a class="ls-item" href="' + p.url + '" role="option">' + img +
                    '<span><span class="ls-title">' + escapeHtml(p.title) + '</span>' +
                    '<span class="ls-meta">' + escapeHtml(p.category || '') + '</span></span>' +
                    '<span class="ls-price">' + faPrice(p.price) + ' تومان</span></a>';
            }).join('');
            html += '<a class="ls-all" href="' + SEARCH_URL + encodeURIComponent(query) + '">مشاهده همه نتایج «' + escapeHtml(query) + '»</a>';
            box.innerHTML = html;
        }

        function escapeHtml(s) {
            return String(s || '').replace(/[&<>"']/g, function (c) {
                return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
            });
        }

        input.addEventListener('input', function () {
            var q = input.value.trim();
            clearTimeout(timer);
            if (q.length < 2) { hide(); return; }
            timer = setTimeout(function () {
                if (q === lastQuery) return;
                lastQuery = q;
                box.innerHTML = '<div class="ls-spinner"><i class="fa fa-spinner fa-spin"></i> در حال جست‌وجو…</div>';
                show();
                fetch(SEARCH_URL + encodeURIComponent(q) + '&ajax=1', {
                    headers: { 'X-Requested-With': 'XMLHttpRequest' }
                })
                    .then(function (r) { return r.json(); })
                    .then(function (data) { render(data.results || [], q); })
                    .catch(function () { hide(); });
            }, 280);
        });

        // بستن با کلیک بیرون
        document.addEventListener('click', function (e) {
            if (!wrap.contains(e.target)) hide();
        });
        // بستن با Esc
        input.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') hide();
        });
    }

    var SEARCH_URL = window.FM_SEARCH_URL || '/products/product_search/?search=';
    var FALLBACK_IMG = window.FM_FALLBACK_IMG || '/static/img/product_image_not_found.jpg';

    document.querySelectorAll('form.search, .search-nav form').forEach(initLiveSearch);

    /* ---------- ۳) دکمه بازگشت به بالا با حلقه پیشرفت ---------- */
    var stWrap = document.createElement('button');
    stWrap.id = 'fmScrollTop';
    stWrap.type = 'button';
    stWrap.setAttribute('aria-label', 'بازگشت به بالای صفحه');
    stWrap.innerHTML =
        '<svg viewBox="0 0 52 52"><circle cx="26" cy="26" r="24"></circle></svg>' +
        '<i class="fa fa-arrow-up" aria-hidden="true"></i>';
    document.body.appendChild(stWrap);
    var stCircle = stWrap.querySelector('circle');
    var CIRC = 2 * Math.PI * 24;

    function onScroll() {
        var scrollTop = window.scrollY || document.documentElement.scrollTop;
        var height = document.documentElement.scrollHeight - window.innerHeight;
        var progress = height > 0 ? Math.min(scrollTop / height, 1) : 0;
        stCircle.style.strokeDashoffset = String(CIRC * (1 - progress));
        if (scrollTop > 300) stWrap.classList.add('show');
        else stWrap.classList.remove('show');
    }
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
    stWrap.addEventListener('click', function () {
        window.scrollTo({ top: 0, behavior: 'smooth' });
    });

    /* ---------- ۴) خبرنامه ---------- */
    var nlForm = document.getElementById('fmNewsletterForm');
    if (nlForm) {
        var status = document.getElementById('fmNlStatus');
        nlForm.addEventListener('submit', function (e) {
            e.preventDefault();
            var email = nlForm.querySelector('input[name="email"]').value.trim();
            if (!email || email.indexOf('@') < 1) {
                status.textContent = 'لطفاً یک ایمیل معتبر وارد کنید.';
                status.className = 'fm-nl-status err';
                return;
            }
            var btn = nlForm.querySelector('button');
            btn.disabled = true;
            var oldText = btn.textContent;
            btn.textContent = 'در حال ثبت…';
            var csrf = '';
            try {
                document.cookie.split(';').forEach(function (c) {
                    var parts = c.trim().split('=');
                    if (parts[0] === 'csrftoken') csrf = parts[1];
                });
            } catch (e) {}
            fetch(NL_URL, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': csrf
                },
                body: JSON.stringify({ email: email })
            })
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    status.textContent = data.message || 'ثبت شد.';
                    status.className = 'fm-nl-status ' + (data.ok ? 'ok' : 'err');
                    if (data.ok) nlForm.querySelector('input[name="email"]').value = '';
                })
                .catch(function () {
                    status.textContent = 'خطا در ارتباط با سرور؛ دوباره تلاش کنید.';
                    status.className = 'fm-nl-status err';
                })
                .finally(function () {
                    btn.disabled = false;
                    btn.textContent = oldText;
                });
        });
    }
    var NL_URL = window.FM_NL_URL || '/newsletter/subscribe/';

    /* ---------- ۵) سال شمسی جاری در فوتر ---------- */
    document.querySelectorAll('.fm-jalali-year').forEach(function (el) {
        try {
            var year = new Intl.DateTimeFormat('fa-IR', { year: 'numeric' }).format(new Date());
            el.textContent = year.replace(/[^۰-۹0-9]/g, '');
        } catch (e) { el.textContent = '۱۴۰۵'; }
    });

    /* ---------- ۶) نمایش/پنهان‌کردن رمز عبور ---------- */
    document.addEventListener('click', function (e) {
        var btn = e.target.closest('.fm-pass-toggle');
        if (!btn) return;
        var input = document.getElementById(btn.getAttribute('data-target'));
        if (!input) return;
        var show = input.type === 'password';
        input.type = show ? 'text' : 'password';
        btn.setAttribute('aria-label', show ? 'پنهان‌کردن رمز عبور' : 'نمایش رمز عبور');
        var icon = btn.querySelector('i');
        if (icon) icon.className = show ? 'fa fa-eye-slash' : 'fa fa-eye';
    });

    /* ---------- ۷) بستن خودکار پیام‌های موفقیت ---------- */
    document.querySelectorAll('.fm-messages .alert-success').forEach(function (el) {
        setTimeout(function () {
            el.style.transition = 'opacity .4s ease, transform .4s ease';
            el.style.opacity = '0';
            el.style.transform = 'translateY(-6px)';
            setTimeout(function () { el.remove(); }, 420);
        }, 6000);
    });
})();
