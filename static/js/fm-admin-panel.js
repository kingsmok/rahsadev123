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
        syncButtons();
        // نمودارها رنگ‌هایشان را با تم عوض می‌کنند
        document.dispatchEvent(new CustomEvent('fm-theme-change', { detail: { theme: theme } }));
    }

    function setNav(open) {
        document.body.classList.toggle('ap-nav-open', open);
        document.querySelectorAll('[data-ap-open-nav]').forEach(function (button) {
            button.setAttribute('aria-expanded', open ? 'true' : 'false');
        });
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
                setNav(!document.body.classList.contains('ap-nav-open'));
            });
        });

        document.querySelectorAll('[data-ap-close-nav]').forEach(function (element) {
            element.addEventListener('click', function () {
                setNav(false);
            });
        });

        document.addEventListener('keydown', function (event) {
            if (event.key === 'Escape') {
                setNav(false);
            }
        });
    });
})();
