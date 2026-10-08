{% load static %}
/* فایل‌مارکت PWA service worker — intentionally conservative for a storefront.
   Only public, versioned UI assets are cached. Authenticated responses, carts,
   downloads and payment requests always stay on the network. */
const CACHE_NAME = 'filemarket-shell-v1';
const OFFLINE_URL = '/offline/';
const APP_SHELL = [
  OFFLINE_URL,
  '{% static "css/bootstrap.min.css" %}',
  '{% static "css/modern-2026.css" %}',
  '{% static "css/fm-design-system.css" %}',
  '{% static "css/fm-ui-audit.css" %}',
  '{% static "js/modern-2026.js" %}',
  '{% static "img/pwa/icon-192.png" %}',
  '{% static "fonts/vazirmatn/Vazirmatn-FD-Regular.woff2" %}'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(APP_SHELL))
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

  // Static application shell: cache first, update cache in the background.
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.match(request).then(cached => {
        const network = fetch(request).then(response => {
          if (response && response.ok) {
            const copy = response.clone();
            caches.open(CACHE_NAME).then(cache => cache.put(request, copy));
          }
          return response;
        });
        return cached || network;
      })
    );
  }
});
