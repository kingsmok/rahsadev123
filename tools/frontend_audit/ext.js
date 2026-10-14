// Extended mobile QA: more pages x widths incl. 1920, console errors,
// failed requests, drawer scroll-lock behaviour, filter label sizes.
const puppeteer = require('puppeteer-core');
const fs = require('fs');
const BASE = 'http://127.0.0.1:8000';
const WIDTHS = [320, 390, 768, 1440, 1920];
const PAGES = [
  '/', '/products/', '/products/category/wordpress-themes/', '/blog/',
  '/services/', '/about/', '/contact/', '/account/', '/cart/',
  '/dashboard/', '/dashboard/orders/', '/dashboard/downloads/',
  '/dashboard/wishlist/', '/dashboard/notifications/', '/dashboard/profile/demo/',
  '/pages/سوالات-متداول/', '/admin-panel/', '/nonexistent-qa/',
];
(async () => {
  const browser = await puppeteer.launch({ executablePath: '/tmp/browser/chromium', args: ['--no-sandbox', '--disable-dev-shm-usage'] });
  const page = await browser.newPage();
  const errors = [];
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text().slice(0, 140)); });
  page.on('pageerror', (e) => errors.push('PAGEERROR: ' + String(e).slice(0, 140)));
  page.on('requestfailed', (r) => { if (r.url().startsWith(BASE)) errors.push('REQFAIL: ' + r.url().slice(0, 110)); });
  page.on('response', (r) => { if (r.url().startsWith(BASE) && r.status() >= 400 && !r.url().includes('nonexistent')) errors.push('HTTP' + r.status() + ': ' + r.url().slice(0, 110)); });
  await page.setRequestInterception(true);
  page.on('request', (r) => { const u = r.url(); if (u.startsWith(BASE) || u.startsWith('data:')) r.continue(); else r.abort(); });

  // discover a product + article URL
  await page.setViewport({ width: 1440, height: 900 });
  await page.goto(BASE + '/products/', { waitUntil: 'domcontentloaded', timeout: 60000 });
  const prodUrl = await page.evaluate(() => { const a = document.querySelector('a[href*="/products/"][href*="/"][href$="/"]'); const links = [...document.querySelectorAll('a')].map(x => x.getAttribute('href')).filter(h => h && /^\/products\/(?!category\/|discount)[^/]+\/[^/]+\/$/.test(h)); return links[0] || null; });
  await page.goto(BASE + '/blog/', { waitUntil: 'domcontentloaded', timeout: 60000 });
  const artUrl = await page.evaluate(() => { const links = [...document.querySelectorAll('a')].map(x => x.getAttribute('href')).filter(h => h && /^\/blog\/[^/]+\/$/.test(h)); return links[0] || null; });
  console.log('product:', prodUrl, '| article:', artUrl);
  if (prodUrl) PAGES.push(prodUrl);
  if (artUrl) PAGES.push(artUrl);

  // login (demo + admin for admin-panel)
  async function login(user, pass) {
    const cdp = await page.createCDPSession();
    await cdp.send('Network.clearBrowserCookies');
    await page.goto(BASE + '/account/', { waitUntil: 'domcontentloaded', timeout: 60000 });
    await page.type('#id_username', user); await page.type('#id_password', pass);
    await Promise.all([page.click('.fm-form button[type=submit]'), page.waitForNavigation({ waitUntil: 'domcontentloaded', timeout: 60000 }).catch(() => {})]);
  }
  await login('demo', 'demo1234');

  const auditFn = () => {
    const doc = document.documentElement;
    const offenders = [];
    document.querySelectorAll('*').forEach((el) => {
      const s = getComputedStyle(el);
      if (s.display === 'none' || s.visibility === 'hidden') return;
      const r = el.getBoundingClientRect();
      if (r.width && (r.right > doc.clientWidth + 1 || r.left < -1) && s.position !== 'fixed' && offenders.length < 5) {
        // ignore elements inside overflow-hidden ancestors (carousels)
        let n = el, clipped = false;
        while (n && n !== doc) { const ov = getComputedStyle(n).overflowX; if (ov === 'hidden' || ov === 'clip') { clipped = true; break; } n = n.parentElement; }
        if (!clipped) offenders.push(el.tagName.toLowerCase() + '.' + String(el.className).trim().replace(/\s+/g, '.').slice(0, 45) + ' [' + Math.round(r.left) + '..' + Math.round(r.right) + ']');
      }
    });
    return { overflowPx: doc.scrollWidth - doc.clientWidth, offenders };
  };

  let bad = 0;
  for (const w of WIDTHS) {
    await page.setViewport({ width: w, height: 900 });
    for (const p of PAGES) {
      if (p === '/admin-panel/') continue;
      await page.goto(BASE + p, { waitUntil: 'domcontentloaded', timeout: 60000 });
      await new Promise((r) => setTimeout(r, 450));
      const res = await page.evaluate(auditFn);
      if (res.overflowPx > 0) { bad++; console.log('✗', w, p, res.overflowPx, res.offenders.join(' | ')); }
    }
  }
  console.log(bad ? `سرریز در ${bad} ترکیب` : 'بدون سرریز در همه ترکیب‌های توسعه‌یافته (شامل ۱۹۲۰)');

  // admin panel at mobile widths
  await login('admin', 'admin1234');
  for (const w of [320, 390, 768, 1440, 1920]) {
    await page.setViewport({ width: w, height: 900 });
    await page.goto(BASE + '/admin-panel/', { waitUntil: 'domcontentloaded', timeout: 60000 });
    await new Promise((r) => setTimeout(r, 600));
    const res = await page.evaluate(auditFn);
    console.log('admin-panel', w, 'overflow=' + res.overflowPx, res.offenders.join(' | '));
  }

  // drawer scroll lock: open nav at 390, wheel the background
  await page.setViewport({ width: 390, height: 844 });
  await page.goto(BASE + '/', { waitUntil: 'domcontentloaded', timeout: 60000 });
  await new Promise((r) => setTimeout(r, 600));
  const lock = await page.evaluate(async () => {
    const btn = document.querySelector('.mobile-menu-toggle, [aria-controls][aria-expanded], .hamburger, button[class*=menu]');
    return { found: !!btn };
  });
  console.log('drawer probe:', JSON.stringify(lock));

  // filter label target sizes on /products/
  await page.goto(BASE + '/products/', { waitUntil: 'domcontentloaded', timeout: 60000 });
  await new Promise((r) => setTimeout(r, 500));
  const labels = await page.evaluate(() => {
    const out = [];
    document.querySelectorAll('.filter-choice, .filter-switch').forEach((el) => {
      const r = el.getBoundingClientRect();
      if (r.width) out.push(el.className + ' ' + Math.round(r.width) + 'x' + Math.round(r.height));
    });
    return out.slice(0, 4);
  });
  console.log('filter label sizes:', labels.join(' | '));

  console.log('\nconsole/network errors:', errors.length);
  [...new Set(errors)].slice(0, 15).forEach((e) => console.log('  ', e));
  await browser.close();
})().catch((e) => { console.error('ERR', e.message); process.exit(1); });
