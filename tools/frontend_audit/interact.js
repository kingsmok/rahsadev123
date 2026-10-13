const puppeteer=require('puppeteer-core');
(async()=>{
 const browser=await puppeteer.launch({executablePath:'/tmp/browser/chromium',headless:'shell',args:['--no-sandbox','--disable-dev-shm-usage','--disable-gpu'],env:{...process.env,LD_LIBRARY_PATH:'/tmp/browser/al2023/lib'}});
 const page=await browser.newPage();
 await page.setRequestInterception(true);
 page.on('request',r=>{const u=r.url(); if(u.startsWith('http://127.0.0.1:8000')||u.startsWith('data:'))r.continue(); else r.abort();});
 const dev=puppeteer.KnownDevices['iPhone 12'];
 await page.emulate(dev);
 await page.goto('http://127.0.0.1:8000/',{waitUntil:'networkidle2'});
 const snap=()=>page.evaluate(()=>({
   navOpen: document.documentElement.classList.contains('nav-open'),
   cartOpen: document.documentElement.classList.contains('cart-drawer-open'),
   bodyOverflow: getComputedStyle(document.body).overflow,
   toggleExpanded: (document.querySelector('.navbar-toggler,[data-toggle=collapse]')||{}).getAttribute?.('aria-expanded'),
 }));
 // hamburger
 const tog=await page.$('.navbar-toggler, [data-toggle="collapse"], .mobile-menu-toggle');
 console.log('دکمه همبرگر یافت شد:', !!tog);
 if(tog){ await tog.tap(); await new Promise(r=>setTimeout(r,600)); console.log('پس از لمس همبرگر:',JSON.stringify(await snap())); 
   // Escape
   await page.keyboard.press('Escape'); await new Promise(r=>setTimeout(r,400)); console.log('پس از Escape:',JSON.stringify(await snap()));
 }
 // cart drawer via trigger
 const ct=await page.$('[data-cart-open], .js-cart-open, a[href="/cart/"].header-action');
 console.log('محرک سبد یافت شد:', !!ct);
 // resize while menu open
 if(tog){ await tog.tap(); await new Promise(r=>setTimeout(r,500));
   await page.setViewport({width:1280,height:900}); await new Promise(r=>setTimeout(r,500));
   console.log('تغییر اندازه به دسکتاپ با منوی باز:',JSON.stringify(await snap()));
   // landscape
   await page.setViewport({width:844,height:390}); await new Promise(r=>setTimeout(r,400));
   const land=await page.evaluate(()=>({overflow:document.documentElement.scrollWidth-document.documentElement.clientWidth, headerH:Math.round(document.querySelector('nav.header-responsive')?.getBoundingClientRect().height||0), vh:innerHeight}));
   console.log('حالت افقی 844x390:',JSON.stringify(land), JSON.stringify(await snap()));
 }
 await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
