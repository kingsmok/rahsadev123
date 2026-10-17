/* «فایل محصول» در فرم محصول: فقط فیلدهای حالت انتخاب‌شده نمایش داده می‌شوند —
   «آپلود فایل» ← فیلد فایل؛ «لینک دانلود» ← لینک و حجم فایل. */
(function () {
    'use strict';

    function setVisible(container, selector, visible) {
        container.querySelectorAll(selector).forEach(function (row) {
            row.style.display = visible ? '' : 'none';
        });
    }

    function sync(container) {
        var checked = container.querySelector('.field-source input[type="radio"]:checked');
        var mode = checked ? checked.value : 'upload';
        setVisible(container, '.field-file', mode === 'upload');
        setVisible(container, '.field-external_url, .field-link_size_mb', mode === 'link');
    }

    function init(root) {
        (root || document).querySelectorAll('.inline-related').forEach(function (container) {
            if (container.querySelector('.field-source')) sync(container);
        });
    }

    document.addEventListener('change', function (event) {
        if (!event.target.matches('.field-source input[type="radio"]')) return;
        var container = event.target.closest('.inline-related');
        if (container) sync(container);
    });
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function () { init(); });
    } else {
        init();
    }
    // فرمی که با «افزودن» ساخته می‌شود.
    document.addEventListener('formset:added', function (event) { init(event.target.parentNode || document); });
})();
