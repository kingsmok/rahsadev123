/* Shared, accessible actions for storefront cards and the mini cart. */
(function () {
    'use strict';

    var config = window.FM || {};

    // The cookie first: Django rotates the CSRF token at login, so a tab that
    // was opened before signing in (in another tab) still carries the old
    // token in its forms and every AJAX call from it failed with 403.  The
    // cookie always holds the current secret.
    function csrfToken() {
        var match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
        if (match) return decodeURIComponent(match[1]);
        var input = document.querySelector('input[name="csrfmiddlewaretoken"]');
        return input ? input.value : '';
    }

    function jsonHeaders() {
        return {
            'X-CSRFToken': csrfToken(),
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest',
            'X-Current-Path': window.location.pathname + window.location.search
        };
    }

    function setBadge(selector, count) {
        document.querySelectorAll(selector).forEach(function (badge) {
            var value = parseInt(count, 10) || 0;
            badge.textContent = String(value);
            badge.hidden = value <= 0;
            var link = badge.closest('a');
            if (link && link.dataset.baseLabel === undefined) {
                link.dataset.baseLabel = (link.getAttribute('aria-label') || '').replace(/\s*\(.*\)\s*$/, '');
            }
            if (link && link.dataset.baseLabel) link.setAttribute('aria-label', link.dataset.baseLabel + ' (' + value + ' فایل)');
        });
    }

    function updateCartCount(count) {
        if (count === undefined || count === null) return;
        config.cartCount = count;
        setBadge('[data-cart-count]', count);
    }

    function updateWishlistCount(count) {
        if (count === undefined || count === null) return;
        config.wishlistCount = count;
        setBadge('[data-wishlist-count]', count);
    }
    window.FMUpdateWishlistCount = updateWishlistCount;

    // A session that expired while the tab stayed open: the server answers
    // 401 JSON (core.decorators.login_required_json) instead of a login page.
    function promptLogin(data) {
        return notify({
            title: 'ورود دوباره',
            text: (data && data.message) || 'برای ادامه وارد حساب کاربری شوید.',
            icon: 'warning',
            confirmButtonText: 'ورود',
            confirmButtonColor: '#46a9ae',
            showCancelButton: true,
            cancelButtonText: 'انصراف'
        }).then(function (result) {
            if (result && result.isConfirmed) {
                window.location.assign((data && data.login_url) || ((config.loginUrl || '/account/') + '?next=' + encodeURIComponent(window.location.pathname)));
            }
        });
    }

    function readJson(response) {
        return response.json().catch(function () { return {}; }).then(function (data) {
            if (response.status === 401 && data && data.login_required) {
                var error = new Error(data.message || 'login required');
                error.loginRequired = true;
                error.data = data;
                throw error;
            }
            return data;
        });
    }
    window.FMReadJson = readJson;
    window.FMPromptLogin = promptLogin;
    window.FMJsonHeaders = jsonHeaders;

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

    // The drawer is rendered with the page; after an AJAX add it would keep
    // showing the old contents ("your cart is empty") until a reload.  Swap in
    // a fresh copy of its contents, keeping the <aside> element itself (it is
    // referenced above).  On failure the old drawer stays; the cart page is
    // always correct.
    function refreshCartDrawer() {
        if (!drawer || !config.cartDrawerUrl || !window.DOMParser) return;
        fetch(config.cartDrawerUrl, {headers: {'X-Requested-With': 'XMLHttpRequest'}, credentials: 'same-origin'})
            .then(function (response) {
                if (!response.ok) throw new Error('drawer refresh failed');
                return response.text();
            })
            .then(function (html) {
                var doc = new DOMParser().parseFromString(html, 'text/html');
                var fresh = doc.getElementById('fm-cart-drawer');
                if (fresh) {
                    drawer.innerHTML = fresh.innerHTML;
                    updateCartCount(fresh.getAttribute('data-cart-count'));
                }
            })
            .catch(function () {});
    }
    window.FMRefreshCartDrawer = refreshCartDrawer;

    // Restored from the back/forward cache the page shows the cart as it was
    // when the visitor left it (e.g. before adding a file on another page).
    window.addEventListener('pageshow', function (event) {
        if (event.persisted && config.isAuthenticated) refreshCartDrawer();
    });

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
        // <a> elements ignore ``disabled``: guard double clicks explicitly.
        if (element.getAttribute('aria-busy') === 'true') return;
        var previousLabel = element.getAttribute('aria-label');
        element.disabled = true;
        element.setAttribute('aria-busy', 'true');

        fetch(cartUrl(config.cartAddUrl, productId), {
            method: 'POST',
            credentials: 'same-origin',
            headers: jsonHeaders(),
            body: JSON.stringify({quantity: 1})
        })
            .then(function (response) {
                return readJson(response).then(function (data) {
                    if (!response.ok || !data.success) throw new Error(data.message || 'افزودن فایل به سبد خرید انجام نشد.');
                    return data;
                });
            })
            .then(function (data) {
                element.classList.add('is-added');
                element.setAttribute('aria-label', 'این فایل به سبد خرید افزوده شد');
                updateCartCount(data.cart_count);
                refreshCartDrawer();
                notify({
                    text: data.message || 'فایل با موفقیت به سبد خرید اضافه شد.',
                    icon: data.already_in_cart ? 'info' : 'success',
                    confirmButtonText: 'مشاهدهٔ سبد خرید',
                    confirmButtonColor: '#46a9ae',
                    showCancelButton: true,
                    cancelButtonText: 'ادامهٔ خرید'
                }).then(function (result) {
                    if (result && result.isConfirmed) setCartDrawer(true, element);
                });
            })
            .catch(function (error) {
                if (error.loginRequired) { promptLogin(error.data); return; }
                showError(error.message);
            })
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
            if (removeButton.disabled) return;
            removeButton.disabled = true;
            var row = removeButton.closest('[data-cart-row]') || removeButton.closest('li');
            if (row) row.classList.add('is-removing');
            fetch(cartUrl(config.cartRemoveUrl, itemId), {
                method: 'POST',
                credentials: 'same-origin',
                headers: jsonHeaders(),
                body: '{}'
            })
                .then(function (response) {
                    return readJson(response).then(function (data) {
                        if (!response.ok || !data.success) throw new Error(data.message || 'حذف فایل از سبد خرید انجام نشد.');
                        return data;
                    });
                })
                .then(function (data) {
                    updateCartCount(data.cart_count);
                    // The cart and payment pages show totals and coupon state
                    // computed on the server: reload them.  Elsewhere only the
                    // drawer needs a fresh copy.
                    if (document.querySelector('[data-cart-page]')) {
                        window.location.reload();
                    } else {
                        refreshCartDrawer();
                    }
                })
                .catch(function (error) {
                    removeButton.disabled = false;
                    if (row) row.classList.remove('is-removing');
                    if (error.loginRequired) { promptLogin(error.data); return; }
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
            credentials: 'same-origin',
            headers: jsonHeaders()
        })
            .then(function (response) {
                return readJson(response).then(function (data) {
                    if (!response.ok || data.status !== 'success') throw new Error(data.message || 'حذف فایل از علاقه‌مندی‌ها انجام نشد.');
                    return data;
                });
            })
            .then(function (data) { updateWishlistCount(data.wishlist_count); window.location.reload(); })
            .catch(function (error) {
                wishlistButton.disabled = false;
                if (error.loginRequired) { promptLogin(error.data); return; }
                showError(error.message);
            });
    });
})();

/* ------------------------------------------------------------------
   Share sheet (product and article pages)
   ------------------------------------------------------------------
   The old Bootstrap modal lived inside the product gallery column; its
   backdrop covered it, so «اشتراک‌گذاری» opened a grey screen that could not
   be used and only offered copying the URL.  This sheet is rendered at body
   level and shares to WhatsApp, Telegram, Instagram (native share sheet on
   phones, otherwise copy + open Instagram), X, Facebook, LinkedIn and e-mail. */
(function () {
    'use strict';

    var sheet = document.getElementById('fm-share-sheet');
    if (!sheet) return;
    var backdrop = document.querySelector('.fm-share-backdrop');
    var status = sheet.querySelector('[data-share-status]');
    var nativeButton = sheet.querySelector('[data-share-native]');
    var lastTrigger = null;
    var shareUrl = sheet.getAttribute('data-share-url') || window.location.href;
    var shareTitle = sheet.getAttribute('data-share-title') || document.title;

    if (nativeButton && navigator.share) nativeButton.hidden = false;

    function say(message) {
        if (status) status.textContent = message;
    }

    function open(trigger) {
        lastTrigger = trigger || document.activeElement;
        sheet.hidden = false;
        if (backdrop) backdrop.hidden = false;
        document.documentElement.classList.add('fm-share-open');
        window.requestAnimationFrame(function () { sheet.classList.add('is-open'); if (backdrop) backdrop.classList.add('is-open'); });
        say('');
        var first = sheet.querySelector('.fm-share-sheet__close');
        if (first) window.setTimeout(function () { first.focus(); }, 30);
    }

    function close() {
        sheet.classList.remove('is-open');
        if (backdrop) backdrop.classList.remove('is-open');
        document.documentElement.classList.remove('fm-share-open');
        window.setTimeout(function () { sheet.hidden = true; if (backdrop) backdrop.hidden = true; }, 200);
        if (lastTrigger && typeof lastTrigger.focus === 'function') lastTrigger.focus();
    }

    function copyText(text) {
        if (navigator.clipboard && window.isSecureContext) {
            return navigator.clipboard.writeText(text);
        }
        return new Promise(function (resolve, reject) {
            var area = document.createElement('textarea');
            area.value = text;
            area.setAttribute('readonly', '');
            area.style.position = 'fixed';
            area.style.opacity = '0';
            document.body.appendChild(area);
            area.select();
            var ok = false;
            try { ok = document.execCommand('copy'); } catch (error) { ok = false; }
            area.remove();
            if (ok) { resolve(); } else { reject(new Error('copy failed')); }
        });
    }

    function nativeShare() {
        return navigator.share({title: shareTitle, text: shareTitle, url: shareUrl});
    }

    document.addEventListener('click', function (event) {
        var opener = event.target.closest('[data-share-open]');
        if (opener) {
            event.preventDefault();
            // On phones the system share sheet already lists Instagram,
            // WhatsApp, Telegram, Eitaa, Bale … — but our sheet stays the
            // default so every network is one tap away on desktop too.
            open(opener);
            return;
        }
        if (sheet.hidden) return;
        if (event.target.closest('[data-share-close]')) {
            event.preventDefault();
            close();
            return;
        }
        if (event.target.closest('[data-share-copy]')) {
            event.preventDefault();
            copyText(shareUrl).then(function () { say('لینک در کلیپ‌بورد کپی شد.'); })
                .catch(function () {
                    var input = sheet.querySelector('#fm-share-url-input');
                    if (input) { input.focus(); input.select(); }
                    say('کپی خودکار انجام نشد؛ لینک انتخاب شد، آن را کپی کنید.');
                });
            return;
        }
        if (event.target.closest('[data-share-native]')) {
            event.preventDefault();
            nativeShare().catch(function () {});
            return;
        }
        if (event.target.closest('[data-share-instagram]')) {
            event.preventDefault();
            // Instagram has no web share URL.  Phones: the native sheet
            // offers Instagram Direct/Stories.  Elsewhere: copy the link and
            // open Instagram so it can be pasted into a direct message.
            if (navigator.share) {
                nativeShare().catch(function () {});
                return;
            }
            copyText(shareUrl).then(function () {
                say('لینک کپی شد؛ در اینستاگرام آن را در دایرکت یا استوری جای‌گذاری کنید.');
            }).catch(function () {
                say('لینک را از کادر پایین کپی کنید و در اینستاگرام جای‌گذاری کنید.');
            }).then(function () {
                window.open('https://www.instagram.com/direct/inbox/', '_blank', 'noopener');
            });
        }
    });

    document.addEventListener('keydown', function (event) {
        if (sheet.hidden) return;
        if (event.key === 'Escape') {
            event.preventDefault();
            close();
            return;
        }
        if (event.key !== 'Tab') return;
        var focusable = Array.prototype.filter.call(
            sheet.querySelectorAll('a[href], button:not([disabled]), input'),
            function (item) { return !item.hidden && item.offsetParent !== null; }
        );
        if (!focusable.length) return;
        var first = focusable[0];
        var last = focusable[focusable.length - 1];
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    });
})();

/* ------------------------------------------------------------------
   Mega menu: switch the preview pane with hover/focus of a category.
   ------------------------------------------------------------------ */
(function () {
    'use strict';
    document.querySelectorAll('[data-fm-mega]').forEach(function (mega) {
        function activate(id) {
            mega.querySelectorAll('[data-fm-mega-cat]').forEach(function (item) {
                item.classList.toggle('is-active', item.getAttribute('data-fm-mega-cat') === id);
            });
            mega.querySelectorAll('[data-fm-mega-pane]').forEach(function (pane) {
                var active = pane.getAttribute('data-fm-mega-pane') === id;
                pane.classList.toggle('is-active', active);
                pane.querySelectorAll('a').forEach(function (link) { link.tabIndex = active ? 0 : -1; });
            });
        }
        mega.querySelectorAll('[data-fm-mega-cat]').forEach(function (item) {
            var id = item.getAttribute('data-fm-mega-cat');
            item.addEventListener('mouseenter', function () { activate(id); });
            item.addEventListener('focusin', function () { activate(id); });
        });
        var first = mega.querySelector('[data-fm-mega-cat]');
        if (first) activate(first.getAttribute('data-fm-mega-cat'));
    });
})();

/* Countdown for time-limited home showcases («پایان نمایش»). */
(function () {
    'use strict';
    var nodes = document.querySelectorAll('[data-fm-countdown]');
    if (!nodes.length) return;
    function fa(value) {
        return String(value).replace(/\d/g, function (d) { return '۰۱۲۳۴۵۶۷۸۹'[d]; });
    }
    function pad(value) { return value < 10 ? '0' + value : String(value); }
    function tick() {
        var now = Date.now();
        nodes.forEach(function (node) {
            var end = Date.parse(node.getAttribute('data-fm-countdown'));
            var text = node.querySelector('[data-fm-countdown-text]') || node;
            if (isNaN(end)) { node.hidden = true; return; }
            var left = Math.max(0, Math.floor((end - now) / 1000));
            if (!left) {
                text.textContent = 'به پایان رسید';
                return;
            }
            var days = Math.floor(left / 86400);
            var rest = left % 86400;
            var clock = pad(Math.floor(rest / 3600)) + ':' + pad(Math.floor((rest % 3600) / 60)) + ':' + pad(rest % 60);
            text.textContent = fa((days ? days + ' روز و ' : '') + clock);
        });
    }
    tick();
    window.setInterval(tick, 1000);
})();
