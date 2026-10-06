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
        initCarousel('#bid-s', {
            rtl: true, items: 1, autoplay: true, autoplayTimeout: 5000,
            loop: true, dots: false,
            onInitialized: startProgressBar,
            onTranslate: resetProgressBar,
            onTranslated: startProgressBar
        });

        function startProgressBar() {
            $('.slide-progress').css({width: '100%', transition: 'width 5000ms'});
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

        /* پنل همبرگری موبایل
           قالب قدیمی برای نمایش پنل به کلاس html.nav-open وابسته بود، اما
           اسکریپت قدیمی Now UI دیگر در base.html لود نمی‌شود. Bootstrap فقط
           کلاس collapse/show را تغییر می‌دهد و پنل بیرون صفحه می‌ماند؛ این
           اتصال کوچک، Collapse استاندارد Bootstrap را با پنل و backdrop
           فعلی همگام می‌کند. */
        var $mobileNavigation = $('#navigation');
        var mobileBreakpoint = window.matchMedia ? window.matchMedia('(max-width: 1077px)') : null;

        function isMobileNavigation() {
            return !mobileBreakpoint || mobileBreakpoint.matches;
        }

        function mobileBackdrop() {
            var $backdrop = $('.fm-mobile-nav-backdrop');
            if (!$backdrop.length) {
                $backdrop = $('<div class="fm-mobile-nav-backdrop" aria-hidden="true"></div>').appendTo('body');
                $backdrop.on('click', function () {
                    if ($mobileNavigation.length && $mobileNavigation.hasClass('show')) {
                        $mobileNavigation.collapse('hide');
                    }
                });
            }
            return $backdrop;
        }

        function setMobileNavigation(open) {
            if (!isMobileNavigation()) return;
            $('html').toggleClass('nav-open', open);
            var $backdrop = mobileBackdrop();
            if (open) {
                requestAnimationFrame(function () { $backdrop.addClass('is-visible'); });
            } else {
                $backdrop.removeClass('is-visible');
                setTimeout(function () {
                    if (!$('html').hasClass('nav-open')) $backdrop.remove();
                }, 250);
            }
        }

        if ($mobileNavigation.length && $.fn.collapse) {
            $mobileNavigation
                .on('show.bs.collapse', function () { setMobileNavigation(true); })
                .on('hidden.bs.collapse', function () { setMobileNavigation(false); })
                .on('click', 'a', function () {
                    if (isMobileNavigation() && $mobileNavigation.hasClass('show')) {
                        $mobileNavigation.collapse('hide');
                    }
                });

            $(document).on('keydown', function (event) {
                if (event.key === 'Escape' && isMobileNavigation() && $mobileNavigation.hasClass('show')) {
                    $mobileNavigation.collapse('hide');
                }
            });

            $(window).on('resize', function () {
                if (!isMobileNavigation()) {
                    $('html').removeClass('nav-open');
                    $('.fm-mobile-nav-backdrop').remove();
                }
            });
        }

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
