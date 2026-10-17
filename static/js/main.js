/* Shared storefront enhancements.
   Every feature is guarded so pages that do not use a component never emit a
   console error. Page-specific libraries (for example Owl Carousel) are
   loaded only by the pages that need them. */
(function ($) {
    'use strict';

    if (!$) return;

    function initCarousel(selector, options) {
        if ($.fn.owlCarousel && $(selector).length) {
            $(selector).owlCarousel(options);
        }
    }

    $(function () {
        // Slide duration comes from «ویترین‌های صفحهٔ اصلی» in the admin.
        var bidDelay = (parseInt($('#bid-s').attr('data-autoplay-seconds'), 10) || 5) * 1000;
        var bidCount = $('#bid-s > .item').length;
        // Desktop: one product beside the offers. Tablet/phone (where the theme
        // hides the offers carousel): a full-width row of 2–4 products. Looping,
        // arrows and autoplay only when there are more products than fit.
        function bidAt(perView) {
            var items = Math.max(1, Math.min(perView, bidCount));
            var moves = bidCount > items;
            return {items: items, loop: moves, nav: moves, autoplay: moves};
        }
        initCarousel('#bid-s', {
            rtl: true, items: 1, margin: 12, autoplay: bidCount > 1, autoplayTimeout: bidDelay,
            autoplayHoverPause: true, loop: bidCount > 1, dots: false,
            nav: bidCount > 1,
            responsive: {0: bidAt(2), 576: bidAt(3), 820: bidAt(4), 1078: bidAt(1)},
            navText: ['<span aria-hidden="true">›</span><span class="fm-sr-only">قبلی</span>', '<span aria-hidden="true">‹</span><span class="fm-sr-only">بعدی</span>'],
            onInitialized: startProgressBar,
            onTranslate: resetProgressBar,
            onTranslated: startProgressBar,
            onResized: startProgressBar
        });

        function startProgressBar(event) {
            var owl = event && event.relatedTarget;
            if (bidCount < 2 || (owl && owl.settings && !owl.settings.autoplay)) {
                resetProgressBar();
                return;
            }
            $('.slide-progress').css({width: '100%', transition: 'width ' + bidDelay + 'ms linear'});
        }

        function resetProgressBar() {
            $('.slide-progress').css({width: 0, transition: 'width 0s'});
        }

        var productCarouselOptions = {
            rtl: true,
            margin: 10,
            nav: true,
            navText: ['<i class="now-ui-icons arrows-1_minimal-right"></i>', '<i class="now-ui-icons arrows-1_minimal-left"></i>'],
            dots: false,
            responsiveClass: true,
            responsive: {
                0: {items: 2, slideBy: 1},
                576: {items: 2, slideBy: 1},
                768: {items: 4, slideBy: 2},
                992: {items: 5, slideBy: 2},
                1400: {items: 6, slideBy: 3}
            }
        };
        initCarousel('.product-carousel', productCarouselOptions);
        initCarousel('.product-carousel-catgory', $.extend(true, {}, productCarouselOptions, {
            responsive: {
                0: {items: 2, slideBy: 1},
                576: {items: 2, slideBy: 1},
                768: {items: 4, slideBy: 2},
                992: {items: 4, slideBy: 2},
                1400: {items: 5, slideBy: 3}
            }
        }));

        initCarousel('.Blog-carousel', {
            rtl: true, margin: 10, nav: true,
            navText: ['<i class="now-ui-icons arrows-1_minimal-right"></i>', '<i class="now-ui-icons arrows-1_minimal-left"></i>'],
            dots: false, responsiveClass: true,
            responsive: {
                0: {items: 2, slideBy: 1}, 576: {items: 2, slideBy: 1},
                768: {items: 3, slideBy: 2}, 992: {items: 4, slideBy: 2},
                1400: {items: 4, slideBy: 3}
            }
        });

        var brandOptions = {
            rtl: true, dots: false, loop: true, autoplay: true,
            autoplayHoverPause: true, smartSpeed: 200,
            responsive: {0: {items: 1}, 480: {items: 2}, 600: {items: 3}, 768: {items: 5}, 992: {items: 6}, 1200: {items: 7}}
        };
        initCarousel('.brand-slider .owl-carousel', brandOptions);
        initCarousel('.brand-slider-cat .owl-carousel', $.extend(true, {}, brandOptions, {
            responsive: {0: {items: 1}, 480: {items: 2}, 600: {items: 3}, 768: {items: 5}, 992: {items: 5}, 1200: {items: 5}}
        }));
        initCarousel('.brand-slider-cat2 .owl-carousel', $.extend(true, {}, brandOptions, {
            smartSpeed: 600,
            responsive: {0: {items: 1}, 480: {items: 2}, 600: {items: 4}, 768: {items: 5}, 992: {items: 5}, 1200: {items: 4}}
        }));
        initCarousel('.slider_main', {
            rtl: true, dots: true, loop: true, autoplay: true, autoplayHoverPause: true,
            smartSpeed: 100, mouseDrag: true, nav: true,
            navText: ["<div class='nav-btn prev-slide'><i class='fa fa-chevron-right'></i></div>", "<div class='nav-btn next-slide'><i class='fa fa-chevron-left'></i></div>"],
            responsive: {0: {items: 1, dots: false}, 480: {items: 1, dots: false}, 600: {items: 1, dots: false}, 767: {items: 1}, 1200: {items: 1}}
        });

        $('.recent-nav .next').on('click', function () { $('.slider_main').trigger('next.owl.carousel'); });
        $('.recent-nav .prev').on('click', function () { $('.slider_main').trigger('prev.owl.carousel'); });

        $('.back-to-top button').on('click', function (event) {
            event.preventDefault();
            $('html, body').animate({scrollTop: 0}, 500);
        });

        var mobileCategory = $('nav.header-responsive li.sub-menu > .mobile-menu-toggle');
        mobileCategory.on('click', function () {
            var $button = $(this);
            var $item = $button.parent('li');
            var isOpen = $item.hasClass('open');
            $item.toggleClass('open', !isOpen).children('ul').stop(true, true).slideToggle(200);
            $button.attr('aria-expanded', String(!isOpen));
            $item.siblings('.sub-menu').removeClass('open').children('ul').stop(true, true).slideUp(200)
                .siblings('.mobile-menu-toggle').attr('aria-expanded', 'false');
        });

        /* پنل همبرگری موبایل (#navigation) حالا با کنترلر مشترک کشوها در
           static/js/fm-drawers.js باز و بسته می‌شود — همان کنترلری که منوی
           کناری فروشگاه، حساب کاربری، وبلاگ و صفحات راهنما را در موبایل
           کشویی می‌کند. اتصال قبلی به Collapse بوت‌استرپ بسته‌شدن را ۲۵۰ms
           معطل می‌کرد و منوی بسته با Tab قابل فوکوس می‌ماند. */

        var desktopCategory = $('.nav-categories-toggle');
        desktopCategory.on('focus', function () {
            // :focus-within keeps the menu visible for keyboard users.
            $(this).attr('aria-expanded', 'true');
        }).on('click', function () {
            var $button = $(this);
            var $item = $button.closest('.list_style');
            var isOpen = $item.hasClass('is-open');
            $item.toggleClass('is-open', !isOpen);
            $button.attr('aria-expanded', String(!isOpen));
        }).on('keydown', function (event) {
            if (event.key === 'Escape') {
                $(this).closest('.list_style').removeClass('is-open');
                $(this).attr('aria-expanded', 'false').trigger('blur');
            }
        });

        // Bootstrap's carousel is only initialised where it exists.
        if ($.fn.carousel && $('.carousel').length) {
            $('.carousel').carousel({interval: 50000});
        }
    });
})(window.jQuery);
