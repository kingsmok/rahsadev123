/* صفحهٔ تکمیل خرید: اعتبارسنجی درجا، حساب اختیاری، نگه‌داشتن اطلاعات و جلوگیری از ارسال دوباره. */
(function () {
    'use strict';

    var form = document.querySelector('[data-checkout-form]');
    if (!form) return;
    var button = form.querySelector('[data-pay-button]');
    var status = form.querySelector('[data-pay-status]');
    var details = document.querySelector('[data-checkout-details]');
    var DRAFT_KEY = 'fm-checkout-draft';

    /* ---------------------------------------------------------- helpers */
    function latinDigits(value) {
        return String(value || '')
            .replace(/[۰-۹]/g, function (d) { return String(d.charCodeAt(0) - 0x06F0); })
            .replace(/[٠-٩]/g, function (d) { return String(d.charCodeAt(0) - 0x0660); });
    }

    // Same rules as notifications.sms.normalize_mobile on the server.
    function normaliseMobile(value) {
        var digits = latinDigits(value).replace(/[^\d+]/g, '');
        if (digits.indexOf('+98') === 0) digits = '0' + digits.slice(3);
        else if (digits.indexOf('0098') === 0) digits = '0' + digits.slice(4);
        else if (digits.indexOf('98') === 0 && digits.length === 12) digits = '0' + digits.slice(2);
        else if (digits.indexOf('9') === 0 && digits.length === 10) digits = '0' + digits;
        return /^09\d{9}$/.test(digits) ? digits : '';
    }

    function field(name) { return document.querySelector('[name="' + name + '"][form="payment-start-form"]'); }

    function setError(input, message) {
        if (!input) return;
        var box = document.querySelector('[data-error-for="' + input.name + '"]');
        if (box) box.textContent = message || '';
        input.classList.toggle('is-invalid', !!message);
        if (message) input.setAttribute('aria-invalid', 'true');
        else input.removeAttribute('aria-invalid');
    }

    var validators = {
        mobile: function (input) {
            var raw = input.value.trim();
            if (!raw) return 'شماره موبایل را وارد کنید؛ رسید و پیگیری سفارش با همین شماره انجام می‌شود.';
            var mobile = normaliseMobile(raw);
            if (!mobile) return 'شماره موبایل معتبر نیست؛ مثل 09121234567';
            input.value = mobile;
            return '';
        },
        email: function (input) {
            var value = input.value.trim();
            input.value = value;
            if (!value) return '';
            return /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(value) ? '' : 'ایمیل واردشده معتبر نیست؛ مثل name@example.com';
        },
        password: function (input) {
            var account = document.querySelector('[data-create-account]');
            if (!account || !account.checked) return '';
            if (!input.value) return 'برای ساخت حساب یک رمز عبور انتخاب کنید (حداقل ۸ کاراکتر).';
            return input.value.length < 8 ? 'رمز عبور باید حداقل ۸ کاراکتر باشد.' : '';
        }
    };

    function validate(input) {
        var check = validators[input.getAttribute('data-validate')];
        var message = check ? check(input) : '';
        setError(input, message);
        return !message;
    }

    /* ----------------------------------------------- guest buyer details */
    if (details) {
        var inputs = details.querySelectorAll('[data-validate]');
        inputs.forEach(function (input) {
            // Validate when the buyer leaves a field, then live while they fix it.
            input.addEventListener('blur', function () { if (input.value || input.required) validate(input); });
            input.addEventListener('input', function () {
                if (input.classList.contains('is-invalid')) validate(input);
                saveDraft();
            });
        });

        var account = details.querySelector('[data-create-account]');
        var passwordBox = details.querySelector('[data-account-password]');
        var syncAccount = function () {
            if (!account || !passwordBox) return;
            passwordBox.hidden = !account.checked;
            var password = passwordBox.querySelector('input');
            if (password) {
                password.required = account.checked;
                if (!account.checked) setError(password, '');
            }
        };
        if (account) account.addEventListener('change', function () { syncAccount(); saveDraft(); });

        // What the buyer typed survives going back to the cart and returning
        // (the password is never stored).  The server keeps submitted values too.
        var restoreDraft = function () {
            var draft;
            try { draft = JSON.parse(window.sessionStorage.getItem(DRAFT_KEY) || 'null'); } catch (e) { draft = null; }
            if (!draft) return;
            ['mobile', 'email'].forEach(function (name) {
                var input = field(name);
                if (input && !input.value && draft[name]) input.value = draft[name];
            });
            if (account && draft.create_account && !account.checked) account.checked = true;
        };
        var saveDraft = function () {
            var mobile = field('mobile');
            var email = field('email');
            try {
                window.sessionStorage.setItem(DRAFT_KEY, JSON.stringify({
                    mobile: mobile ? mobile.value : '',
                    email: email ? email.value : '',
                    create_account: !!(account && account.checked)
                }));
            } catch (e) { /* private mode: the server-side copy still applies */ }
        };
        restoreDraft();
        syncAccount();
    }

    /* ------------------------------------- mobile for instalment payments */
    // Signed-in customers: the instalment gateways need a mobile number.
    (function () {
        var mobileField = document.querySelector('[data-mobile-field]');
        var note = document.querySelector('[data-mobile-note]');
        var radios = document.querySelectorAll('input[name="gateway"]');
        var hasMobile = !!note;
        var forceField = false;
        function sync() {
            var selected = document.querySelector('input[name="gateway"]:checked');
            var needs = selected && selected.getAttribute('data-needs-mobile') === '1';
            if (mobileField) {
                mobileField.hidden = !needs || (hasMobile && !forceField);
                var input = mobileField.querySelector('input');
                if (input) input.required = !!needs && (!hasMobile || forceField);
            }
            if (note) note.hidden = !needs || forceField;
        }
        radios.forEach(function (radio) { radio.addEventListener('change', sync); });
        var change = document.querySelector('[data-change-mobile]');
        if (change) change.addEventListener('click', function () {
            forceField = true;
            sync();
            var input = mobileField && mobileField.querySelector('input');
            if (input) input.focus();
        });
        sync();
    })();

    /* -------------------------------- submit: validation + loading state */
    var submitting = false;

    function setBusy(busy) {
        submitting = busy;
        if (!button) return;
        button.classList.toggle('is-busy', busy);
        button.setAttribute('aria-busy', busy ? 'true' : 'false');
        if (busy) button.setAttribute('aria-disabled', 'true');
        else button.removeAttribute('aria-disabled');
        if (status) status.textContent = busy ? 'در حال انتقال به درگاه پرداخت؛ لطفاً صبر کنید.' : '';
    }

    form.addEventListener('submit', function (event) {
        // A second click while the first request is on its way must not send
        // another payment request (the server also reuses the open payment).
        if (submitting) { event.preventDefault(); return; }
        if (details) {
            var firstInvalid = null;
            details.querySelectorAll('[data-validate]').forEach(function (input) {
                if (input.closest('[hidden]')) return;
                if (!validate(input) && !firstInvalid) firstInvalid = input;
            });
            if (firstInvalid) {
                event.preventDefault();
                firstInvalid.focus();
                return;
            }
            try { window.sessionStorage.removeItem(DRAFT_KEY); } catch (e) { /* ignore */ }
        }
        var mobileField = document.querySelector('[data-mobile-field]');
        if (mobileField && !mobileField.hidden) {
            var mobileInput = mobileField.querySelector('input');
            if (mobileInput && mobileInput.required && !normaliseMobile(mobileInput.value)) {
                event.preventDefault();
                mobileInput.focus();
                return;
            }
        }
        setBusy(true);
    });

    // Coming back from the gateway with the browser's Back button restores this
    // page from the back/forward cache: make the button usable again.
    window.addEventListener('pageshow', function (event) {
        if (event.persisted) setBusy(false);
    });
})();
