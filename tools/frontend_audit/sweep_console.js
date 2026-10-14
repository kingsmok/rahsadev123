// Console / CSP / network / overflow sweep across roles and viewports (real Chromium).
// Usage: node sweep_console.js pages.json   (pages.json: [{"path": "/", "roles": ["anon","demo","admin"]}, ...])
const puppeteer = require('puppeteer-core');
const fs = require('fs');
const BASE = 'http://127.0.0.1:8000';
const VIEWPORTS = [{ name: 'mobile', width: 375, height: 812, isMobile: true, hasTouch: true, deviceScaleFactor: 2 },
                   { name: 'desktop', width: 1366, height: 900 }];
const PAGES = JSON.parse(fs.readFileSync(process.argv[2] || 'pages.json', 'utf8'));

async function login(page, user, pass) {
  await page.goto(BASE + '/account/', { waitUntil: 'domcontentloaded' });
  await page.type('#id_username', user); await page.type('#id_password', pass);
  await Promise.all([page.waitForNavigation({ waitUntil: 'domcontentloaded' }), page.click('.fm-form button[type=submit]')]);
}
async function adminLogin(page) {
  await page.goto(BASE + '/admin/login/', { waitUntil: 'domcontentloaded' });
  await page.type('#id_username', 'admin'); await page.type('#id_password', 'admin1234');
  await Promise.all([page.waitForNavigation({ waitUntil: 'domcontentloaded' }), page.click('input[type=submit]')]);
}

(async () => {
  const browser = await puppeteer.launch({
    executablePath: '/tmp/browser/chromium', headless: 'shell',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--disable-gpu'],
    env: { ...process.env, LD_LIBRARY_PATH: '/tmp/browser/al2023/lib' },
  });
  const results = [];
  for (const role of ['anon', 'demo', 'admin']) {
    for (const vp of VIEWPORTS) {
      const ctx = await browser.createBrowserContext();
      const page = await ctx.newPage();
      await page.setViewport(vp);
      if (role === 'demo') await login(page, 'demo', 'demo1234');
      if (role === 'admin') await adminLogin(page);
      for (const p of PAGES.filter((x) => x.roles.includes(role))) {
        const issues = [];
        const onConsole = (m) => { if (['error', 'warning', 'warn'].includes(m.type())) issues.push(`console.${m.type()}: ${m.text().slice(0, 220)}`); };
        const onErr = (e) => issues.push(`pageerror: ${String(e.message || e).slice(0, 220)}`);
        const onFail = (r) => { const t = r.failure() && r.failure().errorText; if (t !== 'net::ERR_ABORTED') issues.push(`requestfailed: ${r.url().slice(0, 120)} ${t}`); };
        const onResp = (r) => { if (r.status() >= 400 && !r.url().includes('favicon')) issues.push(`HTTP ${r.status()}: ${r.url().slice(0, 140)}`); };
        page.on('console', onConsole); page.on('pageerror', onErr); page.on('requestfailed', onFail); page.on('response', onResp);
        await page.evaluateOnNewDocument(() => {
          window.__csp = [];
          document.addEventListener('securitypolicyviolation', (e) => window.__csp.push(`${e.violatedDirective} -> ${e.blockedURI} @${e.sourceFile}:${e.lineNumber}`));
        });
        let status = 0;
        try {
          const resp = await page.goto(BASE + p.path, { waitUntil: 'networkidle2', timeout: 45000 });
          status = resp ? resp.status() : 0;
          await new Promise((r) => setTimeout(r, 400));
          const m = await page.evaluate(() => {
            const doc = document.documentElement;
            const vw = window.innerWidth;
            const off = [];
            for (const el of document.querySelectorAll('body *')) {
              const s = getComputedStyle(el);
              if (s.display === 'none' || s.visibility === 'hidden' || s.position === 'fixed') continue;
              const r = el.getBoundingClientRect();
              if (r.width === 0 || r.height === 0 || r.right <= 0 || r.left >= vw) continue;
              const out = Math.max(r.right - vw, -r.left);
              if (out > 2 && !el.closest('.owl-stage,.owl-carousel,.fm-cart-drawer,.offcanvas,[aria-hidden="true"]')) {
                off.push(`${el.tagName.toLowerCase()}${el.id ? '#' + el.id : ''}${typeof el.className === 'string' && el.className ? '.' + el.className.trim().split(/\s+/).slice(0, 2).join('.') : ''} out=${Math.round(out)}px`);
              }
            }
            return { overflow: doc.scrollWidth - doc.clientWidth, offenders: off.slice(0, 4), csp: window.__csp || [], title: document.title };
          });
          if (m.overflow > 1) issues.push(`horizontal overflow ${m.overflow}px: ${m.offenders.join(' | ')}`);
          else if (m.offenders.length) issues.push(`clipped (no scroll): ${m.offenders.join(' | ')}`);
          m.csp.forEach((v) => issues.push('CSP: ' + v));
        } catch (e) { issues.push('NAV ERROR ' + e.message.split('\n')[0]); }
        page.off('console', onConsole); page.off('pageerror', onErr); page.off('requestfailed', onFail); page.off('response', onResp);
        results.push({ role, vp: vp.name, path: p.path, status, issues: [...new Set(issues)] });
        process.stdout.write(issues.length ? 'x' : '.');
      }
      await ctx.close();
    }
  }
  fs.writeFileSync('sweep_console.json', JSON.stringify(results, null, 1));
  console.log('\n' + results.filter((r) => r.issues.length).map((r) => `[${r.role}/${r.vp}] ${r.path} (${r.status})\n   ` + r.issues.join('\n   ')).join('\n'));
  console.log(`\n${results.length} renders, ${results.filter((r) => r.issues.length).length} with issues`);
  await browser.close();
})().catch((e) => { console.error('SCRIPT ERROR', e); process.exit(1); });
