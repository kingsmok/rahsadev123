/* Shared, accessible actions for storefront cards and the mini cart. */
(function () {
    'use strict';

    var config = window.FM || {};

    function csrfToken() {
        var input = document.querySelector('input[name="csrfmiddlewaretoken"]');
        if (input) return input.value;
        var match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
        return match ? decodeURIComponent(match[1]) : '';
    }

    function notify(options) {
        if (window.Swal) {
            return window.Swal.fire(options);
        }
        window.alert(options.text || options.title || 'عملیات انجام نشد.');
        return Promise.resolve({isConfirmed: false});
    }

    function showError(message) {
        return notify({title: 'خطا', text: message || 'مشکلی در ارتباط با سرور پیش آمد.', icon: 'error', confirmButtonText: 'تأیید', confirmButtonColor: '#d94848'});
    }

    function cartUrl(template, id) {
        return (template || '').replace('{id}', encodeURIComponent(id));
    }

    window.addToCart = function addToCart(element) {
        if (!element) return;
        if (!config.isAuthenticated) {
            notify({
                title: 'ورود به سیستم',
                text: 'برای افزودن فایل به سبد خرید، ابتدا وارد حساب کاربری شوید.',
                icon: 'warning',
                confirmButtonText: 'ورود',
                confirmButtonColor: '#46a9ae',
                showCancelButton: true,
                cancelButtonText: 'انصراف'
            }).then(function (result) {
                if (result && result.isConfirmed) {
                    var next = window.location.pathname + window.location.search;
                    window.location.assign((config.loginUrl || '/account/') + '?next=' + encodeURIComponent(next));
                }
            });
            return;
        }

        var productId = element.getAttribute('data-product-id');
        if (!productId) return;
        var previousLabel = element.getAttribute('aria-label');
        element.disabled = true;
        element.setAttribute('aria-busy', 'true');

        fetch(cartUrl(config.cartAddUrl, productId), {
            method: 'POST',
            headers: {'X-CSRFToken': csrfToken(), 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest'},
            body: JSON.stringify({quantity: 1})
        })
            .then(function (response) {
                return response.json().catch(function () { return {}; }).then(function (data) {
                    if (!response.ok || !data.success) throw new Error(data.message || 'افزودن فایل به سبد خرید انجام نشد.');
                    return data;
                });
            })
            .then(function (data) {
                element.classList.add('is-added');
                element.setAttribute('aria-label', 'این فایل به سبد خرید افزوده شد');
                notify({text: data.message || 'فایل با موفقیت به سبد خرید اضافه شد.', icon: 'success', confirmButtonText: 'تأیید', confirmButtonColor: '#46a9ae'});
            })
            .catch(function (error) { showError(error.message); })
            .finally(function () {
                element.disabled = false;
                element.removeAttribute('aria-busy');
                if (!element.classList.contains('is-added') && previousLabel) element.setAttribute('aria-label', previousLabel);
            });
    };

    document.addEventListener('click', function (event) {
        var addButton = event.target.closest('.js-add-to-cart');
        if (addButton) {
            event.preventDefault();
            window.addToCart(addButton);
            return;
        }

        var removeButton = event.target.closest('.remove-cart-item');
        if (!removeButton) return;
        event.preventDefault();
        var itemId = removeButton.getAttribute('data-item-id');
        if (!itemId) return;
        removeButton.disabled = true;
        fetch(cartUrl(config.cartRemoveUrl, itemId), {
            method: 'POST',
            headers: {'X-CSRFToken': csrfToken(), 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest'},
            body: '{}'
        })
            .then(function (response) {
                return response.json().catch(function () { return {}; }).then(function (data) {
                    if (!response.ok || !data.success) throw new Error(data.message || 'حذف فایل از سبد خرید انجام نشد.');
                    return data;
                });
            })
            .then(function () { window.location.reload(); })
            .catch(function (error) {
                removeButton.disabled = false;
                showError(error.message);
            });
    });
})();
