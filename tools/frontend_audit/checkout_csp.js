// Real-browser check: does the checkout POST -> 302 -> payment gateway survive the CSP?
const puppeteer = require('puppeteer-core');
const BASE = process.env.BASE || 'http://127.0.0.1:8000';

(async () => {
  const browser = await puppeteer.launch({
    executablePath: '/tmp/browser/chromium', headless: 'shell',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--disable-gpu'],
    env: { ...process.env, LD_LIBRARY_PATH: '/tmp/browser/al2023/lib' },
  });
  const page = await browser.newPage();
  const log = [];
  page.on('console', (m) => log.push(`console.${m.type()}: ${m.text()}`));
  page.on('requestfailed', (r) => log.push(`requestfailed: ${r.url()} -> ${r.failure() && r.failure().errorText}`));
  page.on('request', (r) => { if (r.isNavigationRequest()) log.push(`navigate: ${r.method()} ${r.url()}`); });

  // 1) log in through the real form
  await page.goto(BASE + '/account/', { waitUntil: 'domcontentloaded' });
  await page.type('#id_username', 'demo');
  await page.type('#id_password', 'demo1234');
  await Promise.all([page.waitForNavigation({ waitUntil: 'domcontentloaded' }), page.click('.fm-form button[type=submit]')]);

  // 2) put one product in the cart through the real endpoint (same as the button does)
  await page.goto(BASE + '/products/', { waitUntil: 'domcontentloaded' });
  const added = await page.evaluate(async () => {
    const btn = document.querySelector('[data-product-id]');
    const id = btn && btn.getAttribute('data-product-id');
    const csrf = document.cookie.split('; ').find((c) => c.startsWith('csrftoken='));
    const r = await fetch(`/cart/add/${id}/`, { method: 'POST', headers: { 'X-CSRFToken': csrf ? csrf.split('=')[1] : '', 'X-Requested-With': 'XMLHttpRequest' } });
    return { id, status: r.status, body: await r.text() };
  });
  log.push(`add-to-cart: ${JSON.stringify(added).slice(0, 160)}`);

  // 3) open the payment page and submit the real form
  await page.goto(BASE + '/cart/shopping_payment/', { waitUntil: 'domcontentloaded' });
  const csp = await page.evaluate(() => document.querySelector('#payment-start-form') ? 'form-present' : 'form-missing');
  log.push(`payment page: ${csp}`);
  await page.evaluate(() => {
    window.__violations = [];
    document.addEventListener('securitypolicyviolation', (e) => window.__violations.push(`${e.violatedDirective} blocked ${e.blockedURI}`));
  });
  const nav = page.waitForNavigation({ waitUntil: 'domcontentloaded', timeout: 15000 }).then(() => 'navigated').catch((e) => 'no-navigation: ' + e.message.split('\n')[0]);
  await page.click('#payment-start-form button[type=submit]');
  log.push(`after submit: ${await nav}`);
  await new Promise((r) => setTimeout(r, 1500));
  log.push(`final url: ${page.url()}`);
  try { log.push(`violations seen by page: ${JSON.stringify(await page.evaluate(() => window.__violations || []))}`); } catch (e) { log.push('violations: (page context gone) ' + e.message.split('\n')[0]); }
  console.log(log.join('\n'));
  await browser.close();
})().catch((e) => { console.error('SCRIPT ERROR', e); process.exit(1); });
