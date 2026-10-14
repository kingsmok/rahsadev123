const puppeteer=require('puppeteer-core');
(async()=>{
 const browser=await puppeteer.launch({executablePath:'/tmp/browser/chromium',headless:'shell',args:['--no-sandbox','--disable-dev-shm-usage','--disable-gpu'],env:{...process.env,LD_LIBRARY_PATH:'/tmp/browser/al2023/lib'}});
 const page=await browser.newPage();
 await page.setRequestInterception(true);
 page.on('request',r=>{const u=r.url(); if(u.startsWith('http://127.0.0.1:8000')||u.startsWith('data:'))r.continue(); else r.abort();});
 // 1) newsletter at 320
 await page.setViewport({width:320,height:900});
 await page.goto('http://127.0.0.1:8000/products/',{waitUntil:'networkidle2'});
 let nl=await page.evaluate(()=>{
   const f=document.querySelector('#fmNewsletterForm'); const b=f.querySelector('button');
   const rf=f.getBoundingClientRect(), rb=b.getBoundingClientRect();
   return {formLeft:Math.round(rf.left),formW:Math.round(rf.width),btnLeft:Math.round(rb.left),btnRight:Math.round(rb.right),docOverflow:document.documentElement.scrollWidth-document.documentElement.clientWidth};
 });
 console.log('خبرنامه @320:',JSON.stringify(nl));
 // 2) add-to-cart hit area on home carousel @375
 await page.setViewport({width:375,height:900});
 await page.goto('http://127.0.0.1:8000/',{waitUntil:'networkidle2'});
 let cart=await page.evaluate(()=>{
   const out=[];
   for(const b of document.querySelectorAll('.widget-product .product-carousel .search_prod_btn')){
     const r=b.getBoundingClientRect(); if(r.width>0 && r.left>=0 && r.left<375) out.push({w:Math.round(r.width),h:Math.round(r.height)});
   } return out.slice(0,3);
 });
 console.log('دکمه سبد (کاروسل) @375:',JSON.stringify(cart));
 // 3) pass-toggle with coarse pointer @375 login page
 await page.emulateMediaFeatures([{name:'pointer',value:'coarse'}]);
 await page.goto('http://127.0.0.1:8000/account/',{waitUntil:'networkidle2'});
 let pt=await page.evaluate(()=>{
   const t=document.querySelector('.fm-pass-toggle'); if(!t) return 'نبود';
   const r=t.getBoundingClientRect(); return {w:Math.round(r.width),h:Math.round(r.height)};
 });
 console.log('دکمه نمایش رمز (لمسی):',JSON.stringify(pt));
 await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
