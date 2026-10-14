const puppeteer = require('puppeteer-core');
const BASE = 'http://127.0.0.1:8000';
(async () => {
  const browser = await puppeteer.launch({ executablePath: '/tmp/browser/chromium', args: ['--no-sandbox', '--disable-dev-shm-usage'] });
  const page = await browser.newPage();
  await page.setRequestInterception(true);
  page.on('request', (r) => { const u = r.url(); if (u.startsWith(BASE) || u.startsWith('data:')) r.continue(); else r.abort(); });
  await page.setViewport({ width: 390, height: 844 });
  for (const path of ['/', '/products/']) {
    await page.goto(BASE + path, { waitUntil: 'domcontentloaded', timeout: 60000 });
    await new Promise((r) => setTimeout(r, 2500));
    const data = await page.evaluate(() => {
      const res = performance.getEntriesByType('resource').map((e) => ({ name: e.name.split('/').slice(-1)[0].slice(0, 44), size: e.transferSize || e.encodedBodySize || 0, type: e.initiatorType }));
      res.sort((a, b) => b.size - a.size);
      const total = res.reduce((s, x) => s + x.size, 0);
      const imgs = [...document.images].map((i) => ({ alt: i.alt.slice(0, 18), loading: i.loading, w: i.getAttribute('width'), h: i.getAttribute('height'), cw: i.clientWidth, ch: i.clientHeight }));
      return { total, top: res.slice(0, 8), imgCount: imgs.length, lazyCount: imgs.filter((i) => i.loading === 'lazy').length, noDims: imgs.filter((i) => !i.w && !i.h).length, sample: imgs.slice(0, 5) };
    });
    console.log('\n###', path, 'total KB:', Math.round(data.total / 1024), '| images:', data.imgCount, '| lazy:', data.lazyCount, '| without width/height attrs:', data.noDims);
    data.top.forEach((t) => console.log('  ', Math.round(t.size / 1024) + 'KB', t.type, t.name));
    data.sample.forEach((s) => console.log('   img', JSON.stringify(s)));
  }
  await browser.close();
})().catch((e) => { console.error('ERR', e.message); process.exit(1); });
