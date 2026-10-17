/* ═══════════════════════════════════════════════════════════════════════
   پنل مدیریت فایل‌مارکت — کنترل پوسته
   ── حالت شب/روز (هم‌کلید با فروشگاه: fm-theme) و منوی کشویی موبایل
   ═══════════════════════════════════════════════════════════════════════ */
(function () {
    'use strict';

    var root = document.documentElement;
    var STORAGE_KEY = 'fm-theme';

    function currentTheme() {
        return root.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
    }

    function syncButtons() {
        var theme = currentTheme();
        document.querySelectorAll('[data-ap-theme-toggle]').forEach(function (button) {
            var icon = button.querySelector('i');
            var label = button.querySelector('[data-ap-theme-label]');
            button.setAttribute('aria-pressed', theme === 'dark' ? 'true' : 'false');
            if (icon) {
                icon.className = theme === 'dark' ? 'fa-solid fa-sun' : 'fa-solid fa-moon';
            }
            if (label) {
                label.textContent = theme === 'dark' ? 'حالت روز' : 'حالت شب';
            }
        });
    }

    function setTheme(theme) {
        root.setAttribute('data-theme', theme);
        try {
            localStorage.setItem(STORAGE_KEY, theme);
        } catch (error) {
            /* در حالت خصوصی مرورگر دسترسی به localStorage ممکن است نباشد */
        }
        // رنگ نوار مرورگر موبایل با تم هماهنگ شود
        var meta = document.querySelector('meta[name="theme-color"]');
        if (meta) {
            meta.setAttribute('content', theme === 'dark' ? '#0b1720' : '#ffffff');
        }
        syncButtons();
        // نمودارها رنگ‌هایشان را با تم عوض می‌کنند
        document.dispatchEvent(new CustomEvent('fm-theme-change', { detail: { theme: theme } }));
    }

    /* ── منوی کشویی موبایل (زیر ۹۰۰px) — هم‌رفتار با منوی همبرگری فروشگاه:
       فوکوس داخل منو می‌رود و می‌ماند، Esc و کشیدن انگشت به راست می‌بندد،
       صفحهٔ پشت اسکرول نمی‌شود و فوکوس به دکمهٔ منو برمی‌گردد. ── */
    var drawerQuery = window.matchMedia ? window.matchMedia('(max-width: 900px)') : null;
    var FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';
    var lastNavTrigger = null;

    function sidebar() { return document.querySelector('[data-ap-sidebar]'); }
    function navIsOpen() { return document.body.classList.contains('ap-nav-open'); }
    function isDrawerMode() { return !drawerQuery || drawerQuery.matches; }

    function visibleFocusables(container) {
        return Array.prototype.filter.call(container.querySelectorAll(FOCUSABLE), function (element) {
            return element.getClientRects().length && window.getComputedStyle(element).visibility !== 'hidden';
        });
    }

    function setNav(open, options) {
        options = options || {};
        var panel = sidebar();
        if (open && !isDrawerMode()) return;
        if (open === navIsOpen()) return;
        if (open) lastNavTrigger = options.trigger || document.activeElement;
        document.body.classList.toggle('ap-nav-open', open);
        document.querySelectorAll('[data-ap-open-nav]').forEach(function (button) {
            button.setAttribute('aria-expanded', open ? 'true' : 'false');
        });
        if (!panel) return;
        if (open) {
            panel.setAttribute('role', 'dialog');
            panel.setAttribute('aria-modal', 'true');
            window.setTimeout(function () {
                var close = panel.querySelector('[data-ap-close-nav]');
                if (close && navIsOpen()) close.focus();
            }, 40);
        } else {
            panel.removeAttribute('role');
            panel.removeAttribute('aria-modal');
            panel.style.removeProperty('transform');
            panel.style.removeProperty('transition');
            if (options.restoreFocus !== false && lastNavTrigger && document.contains(lastNavTrigger)) {
                lastNavTrigger.focus();
            }
        }
    }

    function trapNavFocus(event) {
        var panel = sidebar();
        if (!panel) return;
        var items = visibleFocusables(panel);
        if (!items.length) return;
        var first = items[0];
        var last = items[items.length - 1];
        if (!panel.contains(document.activeElement)) {
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

    function enableSwipeToClose() {
        var swipe = null;
        document.addEventListener('touchstart', function (event) {
            var panel = sidebar();
            if (!navIsOpen() || !panel || event.touches.length !== 1 || !panel.contains(event.target)) return;
            if (event.target.closest('input, select, textarea')) return;
            var rect = panel.getBoundingClientRect();
            swipe = {
                x: event.touches[0].clientX, y: event.touches[0].clientY, time: Date.now(), distance: 0, mode: null,
                dir: rect.left + rect.width / 2 >= window.innerWidth / 2 ? 1 : -1, width: rect.width || 1
            };
        }, {passive: true});
        document.addEventListener('touchmove', function (event) {
            var panel = sidebar();
            if (!swipe || !panel) return;
            var dx = (event.touches[0].clientX - swipe.x) * swipe.dir;
            var dy = event.touches[0].clientY - swipe.y;
            if (!swipe.mode) {
                if (Math.abs(dx) < 10 && Math.abs(dy) < 10) return;
                swipe.mode = dx > 0 && Math.abs(dx) > Math.abs(dy) * 1.3 ? 'swipe' : 'scroll';
                if (swipe.mode === 'swipe') panel.style.setProperty('transition', 'none', 'important');
            }
            if (swipe.mode !== 'swipe') return;
            swipe.distance = Math.max(0, dx);
            panel.style.setProperty('transform', 'translateX(' + (swipe.distance * swipe.dir) + 'px)', 'important');
        }, {passive: true});
        function end() {
            var panel = sidebar();
            if (!swipe || !panel) { swipe = null; return; }
            var current = swipe;
            swipe = null;
            if (current.mode !== 'swipe') return;
            panel.style.removeProperty('transition');
            panel.style.removeProperty('transform');
            if (current.distance > current.width * 0.3 || (current.distance > 40 && Date.now() - current.time < 300)) {
                setNav(false, {restoreFocus: false});
            }
        }
        document.addEventListener('touchend', end, {passive: true});
        document.addEventListener('touchcancel', end, {passive: true});
    }

    document.addEventListener('DOMContentLoaded', function () {
        syncButtons();

        document.querySelectorAll('[data-ap-theme-toggle]').forEach(function (button) {
            button.addEventListener('click', function () {
                setTheme(currentTheme() === 'dark' ? 'light' : 'dark');
            });
        });

        document.querySelectorAll('[data-ap-open-nav]').forEach(function (button) {
            button.addEventListener('click', function () {
                setNav(!navIsOpen(), {trigger: button});
            });
        });

        document.querySelectorAll('[data-ap-close-nav]').forEach(function (element) {
            element.addEventListener('click', function () {
                setNav(false);
            });
        });

        // لینک‌های منو صفحه را عوض می‌کنند؛ منو بسته می‌شود تا با Back باز برنگردد.
        var panel = sidebar();
        if (panel) {
            panel.addEventListener('click', function (event) {
                if (navIsOpen() && event.target.closest('a[href]')) setNav(false, {restoreFocus: false});
            });
        }

        document.addEventListener('keydown', function (event) {
            if (!navIsOpen()) return;
            if (event.key === 'Escape') {
                event.preventDefault();
                setNav(false);
            } else if (event.key === 'Tab') {
                trapNavFocus(event);
            }
        });

        if (drawerQuery) {
            var onWidthChange = function () { if (!drawerQuery.matches) setNav(false, {restoreFocus: false}); };
            if (drawerQuery.addEventListener) drawerQuery.addEventListener('change', onWidthChange);
            else if (drawerQuery.addListener) drawerQuery.addListener(onWidthChange);
        }
        window.addEventListener('pageshow', function (event) {
            if (event.persisted) setNav(false, {restoreFocus: false});
        });
        enableSwipeToClose();
    });
})();
