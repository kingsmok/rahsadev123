{% load static site_extras %}
/* PWA service worker — intentionally conservative for a storefront.
   Only public, versioned UI assets are cached. Authenticated responses, carts,
   downloads and payment requests always stay on the network.
   The cache name carries the brand version from «تنظیمات سایت»: renaming the
   shop changes this script, so browsers reinstall it and re-cache the offline
   page with the new name instead of keeping the old one forever. */
const CACHE_NAME = 'filemarket-shell-v1-{{ site_brand.version }}';
const OFFLINE_URL = '/offline/';
const APP_SHELL = [
  OFFLINE_URL,
  '{% asset "css/bootstrap.min.css" %}',
  '{% asset "css/modern-2026.css" %}',
  '{% asset "css/fm-design-system.css" %}',
  '{% asset "css/fm-ui-audit.css" %}',
  '{% asset "js/modern-2026.js" %}',
  '{% static "img/pwa/icon-192.png" %}',
  '{% static "fonts/vazirmatn/Vazirmatn-FD-Regular.woff2" %}'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      // 'reload' bypasses the HTTP cache so a reinstall never stores a stale copy.
      .then(cache => cache.addAll(APP_SHELL.map(url => new Request(url, { cache: 'reload' }))))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys
        .filter(key => key.startsWith('filemarket-') && key !== CACHE_NAME)
        .map(key => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', event => {
  const request = event.request;
  const url = new URL(request.url);

  // Never intercept writes, third-party requests, secure downloads or payment flow.
  if (request.method !== 'GET' || url.origin !== self.location.origin ||
      url.pathname.startsWith('/downloads/') || url.pathname.startsWith('/payments/') ||
      url.pathname.startsWith('/cart/') || url.pathname.startsWith('/dashboard/')) {
    return;
  }

  // A navigation is always fetched fresh. The offline page is only a recovery path.
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request).catch(() => caches.match(OFFLINE_URL))
    );
    return;
  }

  // Static files: cache first, refreshed in the background. Pages link CSS/JS
  // with a content hash (?v=…), so an updated file has a new URL and is fetched
  // fresh on the first view; older copies of the same file are dropped.
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.match(request).then(cached => {
        const network = fetch(request).then(response => {
          if (response && response.ok) {
            const copy = response.clone();
            caches.open(CACHE_NAME).then(cache => cache.keys().then(keys => Promise.all(
              keys.filter(key => {
                const old = new URL(key.url);
                return old.pathname === url.pathname && old.search !== url.search;
              }).map(key => cache.delete(key))
            )).then(() => cache.put(request, copy)));
          }
          return response;
        });
        return cached || network;
      })
    );
  }
});
