/* ═══════════════════════════════════════════════════════════════════════
   کشوهای موبایل — منوی همبرگری اصلی و منوی کناری همهٔ صفحه‌ها
   ───────────────────────────────────────────────────────────────────────
   هر عنصری با data-fm-drawer یک «کشو» است:
     data-fm-drawer-media       فقط وقتی این media query برقرار است کشو است
                                (مثلاً فیلترهای فروشگاه زیر ۹۹۲px)؛ در عرض
                                بیشتر همان ستون کناری معمولی می‌ماند.
     data-fm-drawer-root-class  کلاسی که هنگام باز بودن روی <html> می‌نشیند
                                (منوی اصلی: nav-open برای CSS قدیمی‌تر).
   دکمه‌ها: data-fm-drawer-open="<id>" باز/بسته می‌کند و data-fm-drawer-close
   داخل کشو آن را می‌بندد. پس‌زمینهٔ تیره، Esc، کشیدن انگشت به سمت لبه،
   نگه‌داشتن فوکوس داخل کشو، قفل اسکرول صفحه و برگرداندن فوکوس به دکمه برای
   همهٔ کشوها یکسان است.
   ═══════════════════════════════════════════════════════════════════════ */
(function () {
    'use strict';

    var root = document.documentElement;
    var FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), ' +
        'select:not([disabled]), textarea:not([disabled]), summary, [tabindex]:not([tabindex="-1"])';
    var CLOSE_DELAY = 320;   // کمی بیشتر از انیمیشن ۲۸۰ms بسته‌شدن
    var state = {drawer: null, trigger: null, timer: null, backdrop: null};
    var queries = {};

    function mediaFor(drawer) {
        var query = drawer.getAttribute('data-fm-drawer-media');
        if (!query || !window.matchMedia) return null;
        if (!queries[query]) queries[query] = window.matchMedia(query);
        return queries[query];
    }

    function isDrawerMode(drawer) {
        var media = mediaFor(drawer);
        return !media || media.matches;
    }

    function triggersFor(drawer) {
        return document.querySelectorAll('[data-fm-drawer-open="' + drawer.id + '"]');
    }

    function setExpanded(drawer, open) {
        Array.prototype.forEach.call(triggersFor(drawer), function (trigger) {
            trigger.setAttribute('aria-expanded', open ? 'true' : 'false');
        });
    }

    function isVisible(element) {
        if (!element || !element.getClientRects().length) return false;
        return window.getComputedStyle(element).visibility !== 'hidden';
    }

    function focusables(drawer) {
        return Array.prototype.filter.call(drawer.querySelectorAll(FOCUSABLE), function (element) {
            return !element.closest('[hidden], [inert]') && isVisible(element);
        });
    }

    function focusWithoutScroll(element) {
        try {
            element.focus({preventScroll: true});
        } catch (error) {
            element.focus();
        }
    }

    function backdrop() {
        if (!state.backdrop) {
            state.backdrop = document.createElement('div');
            state.backdrop.className = 'fm-drawer-backdrop';
            state.backdrop.setAttribute('aria-hidden', 'true');
            state.backdrop.addEventListener('click', function () { close(); });
        }
        return state.backdrop;
    }

    /* پنل‌های دیگری که هم‌زمان با کشو نباید باز بمانند. */
    function closeOtherOverlays() {
        document.querySelectorAll('.live-search-results.open').forEach(function (box) {
            box.classList.remove('open');
        });
        if (root.classList.contains('cart-drawer-open') && typeof window.FMCloseCartDrawer === 'function') {
            window.FMCloseCartDrawer(false);
        }
    }

    function open(drawer, trigger) {
        if (!drawer || !isDrawerMode(drawer)) return false;
        if (state.drawer === drawer) return true;
        if (state.drawer) close({immediate: true, restoreFocus: false});
        closeOtherOverlays();
        window.clearTimeout(state.timer);

        state.drawer = drawer;
        state.trigger = trigger || document.activeElement;

        // پس‌زمینه هم‌سطحِ خود کشو قرار می‌گیرد تا در همان stacking context
        // درست زیر آن بنشیند (منوی اصلی داخل هدر ثابت است، بقیه داخل صفحه).
        var shade = backdrop();
        drawer.parentNode.insertBefore(shade, drawer);
        var z = parseInt(window.getComputedStyle(drawer).zIndex, 10);
        shade.style.zIndex = isNaN(z) ? '' : String(z - 1);

        root.classList.add('fm-drawer-active');
        drawer.setAttribute('role', 'dialog');
        drawer.setAttribute('aria-modal', 'true');
        // حالت بسته باید یک بار رسم شود، وگرنه انیمیشن ورود دیده نمی‌شود.
        void drawer.offsetWidth;
        var rootClass = drawer.getAttribute('data-fm-drawer-root-class');
        if (rootClass) root.classList.add(rootClass);
        root.classList.add('fm-drawer-open');
        drawer.classList.add('is-open');
        shade.classList.add('is-visible');
        setExpanded(drawer, true);

        window.setTimeout(function () {
            if (state.drawer !== drawer) return;
            var target = drawer.querySelector('[data-fm-drawer-close]');
            if (!isVisible(target)) target = focusables(drawer)[0];
            if (!target) {
                if (!drawer.hasAttribute('tabindex')) drawer.setAttribute('tabindex', '-1');
                target = drawer;
            }
            focusWithoutScroll(target);
        }, 40);
        drawer.dispatchEvent(new CustomEvent('fm-drawer:open', {bubbles: true}));
        return true;
    }

    function close(options) {
        options = options || {};
        var drawer = state.drawer;
        if (!drawer) return;
        var trigger = state.trigger;
        state.drawer = null;
        state.trigger = null;

        drawer.classList.remove('is-open');
        drawer.style.removeProperty('transform');
        drawer.style.removeProperty('transition');
        var rootClass = drawer.getAttribute('data-fm-drawer-root-class');
        if (rootClass) root.classList.remove(rootClass);
        root.classList.remove('fm-drawer-open');
        drawer.removeAttribute('aria-modal');
        drawer.removeAttribute('role');
        setExpanded(drawer, false);

        var shade = state.backdrop;
        if (shade) {
            shade.classList.remove('is-visible');
            shade.style.removeProperty('opacity');
        }
        var finish = function () {
            if (state.drawer) return;   // در این فاصله کشوی دیگری باز شده است
            root.classList.remove('fm-drawer-active');
            if (shade && shade.parentNode) shade.parentNode.removeChild(shade);
        };
        window.clearTimeout(state.timer);
        if (options.immediate) finish();
        else state.timer = window.setTimeout(finish, CLOSE_DELAY);

        if (options.restoreFocus !== false && trigger && document.contains(trigger) && isVisible(trigger)) {
            focusWithoutScroll(trigger);
        }
        drawer.dispatchEvent(new CustomEvent('fm-drawer:close', {bubbles: true}));
    }

    function toggle(drawer, trigger) {
        if (state.drawer === drawer) close();
        else open(drawer, trigger);
    }

    function trapFocus(event) {
        var drawer = state.drawer;
        var items = focusables(drawer);
        if (!items.length) {
            event.preventDefault();
            focusWithoutScroll(drawer);
            return;
        }
        var first = items[0];
        var last = items[items.length - 1];
        var active = document.activeElement;
        if (!drawer.contains(active)) {
            event.preventDefault();
            focusWithoutScroll(event.shiftKey ? last : first);
        } else if (event.shiftKey && active === first) {
            event.preventDefault();
            focusWithoutScroll(last);
        } else if (!event.shiftKey && active === last) {
            event.preventDefault();
            focusWithoutScroll(first);
        }
    }

    document.addEventListener('click', function (event) {
        var opener = event.target.closest('[data-fm-drawer-open]');
        if (opener) {
            var target = document.getElementById(opener.getAttribute('data-fm-drawer-open'));
            if (target && isDrawerMode(target)) {
                event.preventDefault();
                toggle(target, opener);
            }
            return;
        }
        var drawer = state.drawer;
        if (!drawer || !drawer.contains(event.target)) return;
        if (event.target.closest('[data-fm-drawer-close]')) {
            event.preventDefault();
            close();
            return;
        }
        // لینک داخل کشو: کشو بسته می‌شود تا لینک‌های همین صفحه (مثل #packages)
        // زیر پنل باز نمانند. فوکوس به دکمه برنمی‌گردد چون کاربر جای دیگری می‌رود.
        var link = event.target.closest('a[href]');
        if (link && !event.defaultPrevented && link.target !== '_blank' &&
            !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey) {
            close({restoreFocus: false});
        }
    });

    document.addEventListener('keydown', function (event) {
        if (!state.drawer) return;
        if (event.key === 'Escape') {
            event.preventDefault();
            close();
        } else if (event.key === 'Tab') {
            trapFocus(event);
        }
    });

    /* ---- کشیدن انگشت به سمت لبه برای بستن (مثل اپلیکیشن‌ها) ---- */
    var swipe = null;

    document.addEventListener('touchstart', function (event) {
        var drawer = state.drawer;
        if (!drawer || event.touches.length !== 1 || !drawer.contains(event.target)) return;
        // اسلایدر قیمت و فیلدهای فرم خودشان کشیدن افقی لازم دارند.
        if (event.target.closest('input, select, textarea, [data-fm-no-swipe]')) return;
        var rect = drawer.getBoundingClientRect();
        var touch = event.touches[0];
        swipe = {
            drawer: drawer,
            x: touch.clientX,
            y: touch.clientY,
            time: Date.now(),
            dir: rect.left + rect.width / 2 >= window.innerWidth / 2 ? 1 : -1,   // کشوی سمت راست با کشیدن به راست بسته می‌شود
            width: rect.width || 1,
            distance: 0,
            mode: null
        };
    }, {passive: true});

    document.addEventListener('touchmove', function (event) {
        if (!swipe) return;
        if (state.drawer !== swipe.drawer) {
            swipe = null;
            return;
        }
        var touch = event.touches[0];
        var dx = (touch.clientX - swipe.x) * swipe.dir;
        var dy = touch.clientY - swipe.y;
        if (!swipe.mode) {
            if (Math.abs(dx) < 10 && Math.abs(dy) < 10) return;
            swipe.mode = dx > 0 && Math.abs(dx) > Math.abs(dy) * 1.3 ? 'swipe' : 'scroll';
            if (swipe.mode === 'swipe') swipe.drawer.style.setProperty('transition', 'none', 'important');
        }
        if (swipe.mode !== 'swipe') return;
        swipe.distance = Math.max(0, dx);
        swipe.drawer.style.setProperty('transform', 'translate3d(' + (swipe.distance * swipe.dir) + 'px, 0, 0)', 'important');
        if (state.backdrop) state.backdrop.style.opacity = String(Math.max(0, 1 - swipe.distance / swipe.width));
    }, {passive: true});

    function endSwipe() {
        if (!swipe) return;
        var current = swipe;
        swipe = null;
        if (current.mode !== 'swipe' || state.drawer !== current.drawer) return;
        var quick = current.distance > 40 && Date.now() - current.time < 300;
        if (current.distance > current.width * 0.3 || quick) {
            close({restoreFocus: false});
        } else {
            // برگشت نرم به حالت باز
            current.drawer.style.removeProperty('transition');
            current.drawer.style.removeProperty('transform');
            if (state.backdrop) state.backdrop.style.removeProperty('opacity');
        }
    }

    document.addEventListener('touchend', endSwipe, {passive: true});
    document.addEventListener('touchcancel', endSwipe, {passive: true});

    /* عرض صفحه از حالت کشو خارج شد (چرخش تبلت یا تغییر اندازهٔ پنجره): کشو
       بسته می‌شود تا ستون کناری دسکتاپ با ویژگی‌های دیالوگ باقی نماند. */
    function watchMedia() {
        document.querySelectorAll('[data-fm-drawer]').forEach(function (drawer) {
            var media = mediaFor(drawer);
            if (!media || media.fmWatched) return;
            media.fmWatched = true;
            var onChange = function () {
                if (!media.matches && state.drawer && mediaFor(state.drawer) === media) {
                    close({immediate: true, restoreFocus: false});
                }
            };
            if (media.addEventListener) media.addEventListener('change', onChange);
            else if (media.addListener) media.addListener(onChange);
        });
    }

    // برگشت با دکمهٔ Back از bfcache: صفحه نباید با کشوی نیمه‌باز برگردد.
    window.addEventListener('pageshow', function (event) {
        if (event.persisted && state.drawer) close({immediate: true, restoreFocus: false});
    });

    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', watchMedia);
    else watchMedia();

    window.FMDrawers = {
        open: function (id, trigger) { return open(document.getElementById(id), trigger); },
        close: close,
        isOpen: function (id) { return !!state.drawer && (!id || state.drawer.id === id); },
        current: function () { return state.drawer; }
    };
})();
