/* ویرایشگر کد HTML پنل مدیریت با پیش‌نمایش زنده.
   پیش‌نمایش داخل iframe ایزوله (sandbox بدون allow-same-origin) ساخته می‌شود؛
   اسکریپت‌های کد به کوکی و صفحهٔ ادمین دسترسی ندارند. */
(function () {
    'use strict';

    function buildDocument(code, stylesheets) {
        var links = stylesheets.map(function (href) {
            return '<link rel="stylesheet" href="' + href.replace(/"/g, '&quot;') + '">';
        }).join('');
        return '<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8">' +
            '<meta name="viewport" content="width=device-width, initial-scale=1">' +
            '<base href="' + window.location.origin + '/" target="_blank">' + links +
            '<style>html,body{background:#f6f8fb;margin:0}body{padding:16px;font-family:Vazirmatn,Tahoma,sans-serif}</style>' +
            '</head><body><div class="fm-custom-html">' + code + '</div></body></html>';
    }

    function init(editor) {
        var textarea = editor.querySelector('textarea');
        var frame = editor.querySelector('[data-fm-code-preview]');
        if (!textarea || !frame) return;
        var stylesheets = [];
        try { stylesheets = JSON.parse(editor.getAttribute('data-preview-css') || '[]'); } catch (error) { stylesheets = []; }
        var timer = null;

        function render() {
            frame.srcdoc = buildDocument(textarea.value || '<p style="color:#8a94a6">کد HTML را در کادر بنویسید تا پیش‌نمایش آن اینجا نمایش داده شود.</p>', stylesheets);
        }

        function schedule() {
            window.clearTimeout(timer);
            timer = window.setTimeout(render, 350);
        }

        textarea.addEventListener('input', schedule);
        textarea.addEventListener('keydown', function (event) {
            if (event.key === 'Tab' && !event.shiftKey && !event.ctrlKey && !event.metaKey) {
                event.preventDefault();
                var start = textarea.selectionStart;
                var end = textarea.selectionEnd;
                textarea.value = textarea.value.slice(0, start) + '  ' + textarea.value.slice(end);
                textarea.selectionStart = textarea.selectionEnd = start + 2;
                schedule();
            }
        });

        editor.querySelectorAll('[data-mode]').forEach(function (button) {
            button.addEventListener('click', function () {
                editor.setAttribute('data-view', button.getAttribute('data-mode'));
                editor.querySelectorAll('[data-mode]').forEach(function (item) { item.classList.toggle('is-active', item === button); });
                if (button.getAttribute('data-mode') !== 'code') render();
            });
        });
        editor.querySelectorAll('[data-device]').forEach(function (button) {
            button.addEventListener('click', function () {
                frame.style.width = button.getAttribute('data-device');
                editor.querySelectorAll('[data-device]').forEach(function (item) { item.classList.toggle('is-active', item === button); });
            });
        });
        editor.setAttribute('data-view', 'split');
        render();
    }

    function boot() {
        document.querySelectorAll('[data-fm-code-editor]').forEach(init);
    }
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', boot);
    } else {
        boot();
    }
})();
