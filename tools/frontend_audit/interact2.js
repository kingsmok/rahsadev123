// Mobile interaction QA #2: cart drawer, dashboard menu, login error, key pages at 320.
const puppeteer = require('puppeteer-core');
const BASE = 'http://127.0.0.1:8000';
(async () => {
  const browser = await puppeteer.launch({ executablePath: '/tmp/browser/chromium', args: ['--no-sandbox', '--disable-dev-shm-usage'] });
  const page = await browser.newPage();
  await page.setRequestInterception(true);
  page.on('request', (r) => { const u = r.url(); if (u.startsWith(BASE) || u.startsWith('data:')) r.continue(); else r.abort(); });
  await page.setViewport({ width: 390, height: 844 });

  // ۱) کشوی سبد: باز کردن با لمس آیکن سبد در هدر
  await page.goto(BASE + '/', { waitUntil: 'domcontentloaded', timeout: 60000 });
  await new Promise((r) => setTimeout(r, 800));
  const cartBtn = await page.$('.js-cart-drawer-toggle');
  console.log('دکمه سبد:', !!cartBtn);
  if (cartBtn) {
    await cartBtn.tap();
    await new Promise((r) => setTimeout(r, 700));
    const st = await page.evaluate(() => {
      const d = document.querySelector('#fm-cart-drawer, .fm-cart-drawer, [class*=cart-drawer]');
      const r = d ? d.getBoundingClientRect() : null;
      return { exists: !!d, visible: r ? (r.width > 0 && r.right > 0 && r.left < innerWidth) : false,
               rect: r ? [Math.round(r.left), Math.round(r.right)] : null,
               expanded: document.querySelector('.js-cart-drawer-toggle')?.getAttribute('aria-expanded'),
               docOverflow: document.documentElement.scrollWidth - document.documentElement.clientWidth };
    });
    console.log('کشوی سبد پس از لمس:', JSON.stringify(st));
    await page.screenshot({ path: '/tmp/m_cartdrawer.png' });
    await page.keyboard.press('Escape');
    await new Promise((r) => setTimeout(r, 500));
    const st2 = await page.evaluate(() => document.querySelector('.js-cart-drawer-toggle')?.getAttribute('aria-expanded'));
    console.log('پس از Escape، aria-expanded:', st2);
  }

  // ۲) خطای ورود: رمز اشتباه → پیام خطا خوانا و فرم سالم
  await page.goto(BASE + '/account/', { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.type('#id_username', 'demo'); await page.type('#id_password', 'wrongpass');
  await Promise.all([page.click('.fm-form button[type=submit]'), page.waitForNavigation({ waitUntil: 'domcontentloaded', timeout: 60000 }).catch(() => {})]);
  await new Promise((r) => setTimeout(r, 500));
  const err = await page.evaluate(() => {
    const e = document.querySelector('.fm-form .errorlist, .fm-alert, [role=alert], .invalid-feedback, .fm-error');
    return { hasError: !!e, text: e ? e.textContent.trim().slice(0, 60) : null,
             docOverflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
             usernameKept: document.querySelector('#id_username')?.value };
  });
  console.log('خطای ورود:', JSON.stringify(err));
  await page.screenshot({ path: '/tmp/m_loginerr.png' });

  // ۳) ورود درست و منوی داشبورد موبایل
  await page.type('#id_password', 'demo1234');
  // username ممکن است خالی شده باشد
  await page.evaluate(() => { const u = document.querySelector('#id_username'); if (u && !u.value) u.value = 'demo'; });
  await Promise.all([page.click('.fm-form button[type=submit]'), page.waitForNavigation({ waitUntil: 'domcontentloaded', timeout: 60000 }).catch(() => {})]);
  await page.goto(BASE + '/dashboard/', { waitUntil: 'domcontentloaded', timeout: 60000 });
  await new Promise((r) => setTimeout(r, 700));
  const dd = await page.$('.responsive-profile-menu .dropdown-toggle, .responsive-profile-menu button');
  console.log('دکمه منوی داشبورد:', !!dd);
  if (dd) {
    await dd.tap();
    await new Promise((r) => setTimeout(r, 600));
    const menu = await page.evaluate(() => {
      const m = document.querySelector('.responsive-profile-menu .dropdown-menu');
      const r = m ? m.getBoundingClientRect() : null;
      return { open: m ? getComputedStyle(m).display !== 'none' : false,
               inViewport: r ? (r.left >= -1 && r.right <= innerWidth + 1) : false,
               rect: r ? [Math.round(r.left), Math.round(r.right), Math.round(r.height)] : null };
    });
    console.log('منوی داشبورد:', JSON.stringify(menu));
    await page.screenshot({ path: '/tmp/m_dashmenu.png' });
  }

  // ۴) اسکرین‌شات ۳۲۰: جزئیات محصول و سبد
  await page.setViewport({ width: 320, height: 800 });
  await page.goto(BASE + '/products/', { waitUntil: 'domcontentloaded', timeout: 60000 });
  const prod = await page.evaluate(() => { const l = [...document.querySelectorAll('a')].map(x => x.getAttribute('href')).filter(h => h && /^\/products\/(?!category\/|discount)[^/]+\/[^/]+\/$/.test(h)); return l[0]; });
  await page.goto(BASE + prod, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await new Promise((r) => setTimeout(r, 700));
  console.log('جزئیات محصول ۳۲۰ overflow:', await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth));
  await page.screenshot({ path: '/tmp/m_product320.png' });
  await page.goto(BASE + '/cart/', { waitUntil: 'domcontentloaded', timeout: 60000 });
  await new Promise((r) => setTimeout(r, 700));
  console.log('سبد ۳۲۰ overflow:', await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth));
  await page.screenshot({ path: '/tmp/m_cart320.png' });
  await browser.close();
})().catch((e) => { console.error('ERR', e.message); process.exit(1); });
