/*
 * Full responsive sweep with real headless Chromium.
 *
 * Measurements only consider elements that actually intersect the viewport, so
 * off-canvas panels (the mobile nav drawer, the cart drawer, carousel slides
 * parked outside the track) are not reported as overflow.
 */
const puppeteer = require('puppeteer-core');
const fs = require('fs');

const CHROME = '/tmp/browser/chromium';
const BASE = 'http://127.0.0.1:8000';
const WIDTHS = [320, 360, 375, 390, 414, 430, 600, 768, 820, 834, 1024, 1280, 1440];

const PAGES = [
    { path: '/', note: 'خانه' },
    { path: '/products/', note: 'فروشگاه' },
    { path: '/blog/', note: 'وبلاگ' },
    { path: '/about/', note: 'درباره' },
    { path: '/contact/', note: 'تماس' },
    { path: '/account/', note: 'ورود' },
    { path: '/cart/', note: 'سبد' },
    { path: '/dashboard/', note: 'داشبورد' },
    { path: '/dashboard/orders/', note: 'سفارش‌ها' },
    { path: '/admin-panel/', note: 'پنل مدیریت', staff: true },
];

function audit() {
    const vw = window.innerWidth;
    const doc = document.documentElement;
    const res = {
        scrollWidth: doc.scrollWidth,
        clientWidth: doc.clientWidth,
        overflowPx: doc.scrollWidth - doc.clientWidth,
        offenders: [], smallTargets: [], overlaps: [],
    };
    const vis = (el) => {
        const s = getComputedStyle(el);
        if (s.display === 'none' || s.visibility === 'hidden' || s.opacity === '0') return false;
        const r = el.getBoundingClientRect();
        return r.width > 0 && r.height > 0;
    };
    // Only elements that are at least partially on screen.
    const onScreen = (r) => r.right > 0 && r.left < vw;
    const name = (el) => {
        const c = (typeof el.className === 'string' && el.className.trim())
            ? '.' + el.className.trim().split(/\s+/).slice(0, 2).join('.') : '';
        return el.tagName.toLowerCase() + c;
    };

    for (const el of document.querySelectorAll('body *')) {
        if (!vis(el)) continue;
        const r = el.getBoundingClientRect();
        if (!onScreen(r)) continue;
        const out = Math.max(r.right - vw, -r.left);
        if (out > 1) {
            res.offenders.push({ sel: name(el), out: Math.round(out), w: Math.round(r.width), left: Math.round(r.left) });
        }
    }
    res.offenders.sort((a, b) => b.out - a.out);
    res.offenders = res.offenders.slice(0, 8);

    const boxes = [];
    for (const el of document.querySelectorAll('a[href], button:not([disabled]), input:not([type=hidden]), select, textarea')) {
        if (!vis(el)) continue;
        const r = el.getBoundingClientRect();
        if (!onScreen(r) || r.width < 1 || r.height < 1) continue;
        const isInlineText = el.tagName === 'A' &&
            getComputedStyle(el).display === 'inline' && !el.querySelector('img, svg, i');
        boxes.push({ el, r, n: name(el) });
        if ((r.width < 44 || r.height < 44) && !isInlineText) {
            res.smallTargets.push({
                sel: name(el), w: Math.round(r.width), h: Math.round(r.height),
                text: (el.textContent || el.getAttribute('aria-label') || '').trim().slice(0, 24),
            });
        }
    }
    // dedupe by selector+size
    const seen = new Set();
    res.smallTargets = res.smallTargets.filter((t) => {
        const k = t.sel + t.w + t.h;
        if (seen.has(k)) return false; seen.add(k); return true;
    }).slice(0, 10);

    for (let i = 0; i < boxes.length; i++) {
        for (let j = i + 1; j < boxes.length; j++) {
            const a = boxes[i], b = boxes[j];
            if (a.el.contains(b.el) || b.el.contains(a.el)) continue;
            const ox = Math.min(a.r.right, b.r.right) - Math.max(a.r.left, b.r.left);
            const oy = Math.min(a.r.bottom, b.r.bottom) - Math.max(a.r.top, b.r.top);
            if (ox <= 4 || oy <= 4) continue;
            const smaller = Math.min(a.r.width * a.r.height, b.r.width * b.r.height);
            if (smaller <= 0) continue;
            const frac = (ox * oy) / smaller;
            if (frac > 0.6) res.overlaps.push({ pct: Math.round(frac * 100), a: a.n, b: b.n });
        }
    }
    res.overlaps = res.overlaps.slice(0, 6);
    return res;
}

async function login(page, user, pass) {
    await page.goto(BASE + '/account/', { waitUntil: 'networkidle2' });
    const has = await page.$('input[name=username]');
    if (!has) return false;
    await page.type('input[name=username]', user, { delay: 5 });
    await page.type('input[name=password]', pass, { delay: 5 });
    await Promise.all([
        page.waitForNavigation({ waitUntil: 'networkidle2', timeout: 15000 }).catch(() => {}),
        page.click('button[type=submit]'),
    ]);
    return true;
}

(async () => {
    const browser = await puppeteer.launch({
        executablePath: CHROME, headless: 'shell',
        args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--disable-gpu'],
        env: { ...process.env, LD_LIBRARY_PATH: '/tmp/browser/al2023/lib' },
    });

    const results = [];
    for (const role of [{ who: 'مشتری', user: 'demo', pass: 'demo1234' },
                        { who: 'پشتیبان', user: 'admin', pass: 'admin1234' }]) {
        const page = await browser.newPage();
        await page.setRequestInterception(true);
        page.on('request', (r) => {
            const u = r.url();
            if (u.startsWith(BASE) || u.startsWith('data:') || u.startsWith('blob:')) r.continue(); else r.abort();
        });
        await login(page, role.user, role.pass);

        for (const p of PAGES) {
            if (p.staff && role.who !== 'پشتیبان') continue;
            for (const w of WIDTHS) {
                await page.setViewport({ width: w, height: 900 });
                let rec;
                try {
                    await page.goto(BASE + p.path, { waitUntil: 'networkidle2', timeout: 25000 });
                    rec = await page.evaluate(audit);
                } catch (e) { rec = { error: String(e).slice(0, 120) }; }
                rec.path = p.path; rec.note = p.note; rec.width = w; rec.role = role.who;
                results.push(rec);
                const flag = rec.overflowPx > 1 ? '  <-- سرریز افقی' : '';
                console.log(
                    `[${role.who}] ${p.note.padEnd(12)} ${String(w).padStart(4)}px  ` +
                    `overflow=${String(rec.overflowPx ?? '?').padStart(4)}  ` +
                    `بیرون‌زده=${(rec.offenders || []).length}  کوچک=${(rec.smallTargets || []).length}  ` +
                    `هم‌پوشان=${(rec.overlaps || []).length}${flag}`);
            }
        }
        await page.close();
    }
    fs.writeFileSync('/tmp/browser/sweep.json', JSON.stringify(results, null, 1));
    await browser.close();
    console.log('\nذخیره شد');
})().catch((e) => { console.error('FAILED', e); process.exit(1); });
