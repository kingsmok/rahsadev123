// Touch-device emulation: password toggle + tap targets under pointer:coarse.
const puppeteer = require('puppeteer-core');
const BASE = 'http://127.0.0.1:8000';
(async () => {
  const browser = await puppeteer.launch({ executablePath: '/tmp/browser/chromium', args: ['--no-sandbox', '--disable-dev-shm-usage'] });
  const page = await browser.newPage();
  await page.setRequestInterception(true);
  page.on('request', (r) => { const u = r.url(); if (u.startsWith(BASE) || u.startsWith('data:')) r.continue(); else r.abort(); });
  await page.emulate(puppeteer.KnownDevices['iPhone 12']);
  await page.goto(BASE + '/account/', { waitUntil: 'domcontentloaded', timeout: 60000 });
  await new Promise((r) => setTimeout(r, 600));
  const res = await page.evaluate(() => {
    const t = document.querySelector('.fm-pass-toggle');
    const r = t ? t.getBoundingClientRect() : null;
    return { coarse: matchMedia('(pointer: coarse)').matches,
             toggle: r ? Math.round(r.width) + 'x' + Math.round(r.height) : null,
             overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth };
  });
  console.log('iPhone 12 emulation:', JSON.stringify(res));
  await browser.close();
})().catch((e) => { console.error('ERR', e.message); process.exit(1); });
