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

    /* ------------------------------------------------------------------
       Cart drawer
       ------------------------------------------------------------------
       The old mini-cart was a Bootstrap dropdown inside the desktop header.
       A header is a fragile containing/stacking context for a long cart, so
       this controller opens the body-level drawer instead. */
    var drawer = document.getElementById('fm-cart-drawer');
    var lastCartTrigger = null;

    function cartTriggers() {
        return document.querySelectorAll('.js-cart-drawer-toggle');
    }

    function closeMobileNavigation() {
        var navigation = document.getElementById('navigation');
        document.documentElement.classList.remove('nav-open');
        if (navigation && navigation.classList.contains('show') && window.jQuery && window.jQuery.fn.collapse) {
            window.jQuery(navigation).collapse('hide');
        }
    }

    function setCartDrawer(open, trigger) {
        if (!drawer) return;
        if (open) {
            closeMobileNavigation();
            document.querySelectorAll('.live-search-results').forEach(function (item) { item.classList.remove('open'); });
            document.querySelectorAll('.nav-categories-toggle').forEach(function (item) {
                var parent = item.closest('.list_style');
                if (parent) parent.classList.remove('is-open');
                item.setAttribute('aria-expanded', 'false');
            });
            lastCartTrigger = trigger || document.activeElement;
            document.documentElement.classList.add('cart-drawer-open');
            drawer.setAttribute('aria-hidden', 'false');
            cartTriggers().forEach(function (item) { item.setAttribute('aria-expanded', 'true'); });
            var closeButton = drawer.querySelector('[data-cart-drawer-close]');
            window.setTimeout(function () { if (closeButton) closeButton.focus(); }, 20);
        } else {
            document.documentElement.classList.remove('cart-drawer-open');
            drawer.setAttribute('aria-hidden', 'true');
            cartTriggers().forEach(function (item) { item.setAttribute('aria-expanded', 'false'); });
            if (lastCartTrigger && typeof lastCartTrigger.focus === 'function' && document.contains(lastCartTrigger)) {
                lastCartTrigger.focus();
            }
        }
    }

    function cartDrawerIsOpen() {
        return document.documentElement.classList.contains('cart-drawer-open');
    }

    function trapCartDrawerFocus(event) {
        if (!cartDrawerIsOpen() || event.key !== 'Tab' || !drawer) return;
        var focusable = Array.prototype.slice.call(drawer.querySelectorAll(
            'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
        )).filter(function (item) { return item.getAttribute('aria-hidden') !== 'true'; });
        if (!focusable.length) {
            event.preventDefault();
            return;
        }
        var first = focusable[0];
        var last = focusable[focusable.length - 1];
        if (event.shiftKey && document.activeElement === first) {
            event.preventDefault();
            last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
            event.preventDefault();
            first.focus();
        }
    }

    document.addEventListener('keydown', function (event) {
        if (!cartDrawerIsOpen()) return;
        if (event.key === 'Escape') {
            event.preventDefault();
            setCartDrawer(false);
            return;
        }
        trapCartDrawerFocus(event);
    });

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
        var cartTrigger = event.target.closest('.js-cart-drawer-toggle');
        if (cartTrigger) {
            event.preventDefault();
            setCartDrawer(!cartDrawerIsOpen(), cartTrigger);
            return;
        }

        var drawerClose = event.target.closest('[data-cart-drawer-close]');
        if (drawerClose && cartDrawerIsOpen()) {
            event.preventDefault();
            setCartDrawer(false);
            return;
        }

        var addButton = event.target.closest('.js-add-to-cart');
        if (addButton) {
            event.preventDefault();
            window.addToCart(addButton);
            return;
        }

        var removeButton = event.target.closest('.remove-cart-item');
        if (removeButton) {
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
            return;
        }

        var wishlistButton = event.target.closest('.remove-wishlist-item');
        if (!wishlistButton) return;
        event.preventDefault();
        var productId = wishlistButton.getAttribute('data-product-id');
        if (!productId) return;
        wishlistButton.disabled = true;
        fetch(cartUrl(config.wishlistRemoveUrl, productId), {
            method: 'POST',
            headers: {'X-CSRFToken': csrfToken(), 'X-Requested-With': 'XMLHttpRequest'}
        })
            .then(function (response) {
                return response.json().catch(function () { return {}; }).then(function (data) {
                    if (!response.ok || data.status !== 'success') throw new Error(data.message || 'حذف فایل از علاقه‌مندی‌ها انجام نشد.');
                    return data;
                });
            })
            .then(function () { window.location.reload(); })
            .catch(function (error) {
                wishlistButton.disabled = false;
                showError(error.message);
            });
    });
})();
