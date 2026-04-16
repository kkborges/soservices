const { chromium } = require('playwright-core');
(async () => {
  const browser = await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe', headless:true, args:['--ignore-certificate-errors']});
  const page = await browser.newPage({ignoreHTTPSErrors:true});
  await page.goto('https://192.168.0.1/webpages/login.html', {waitUntil:'networkidle', timeout:30000});
  await page.locator('#login-username').fill('admin');
  await page.locator('input[type="password"]:visible').first().fill('@LS1805L1109@fk');
  await page.click('#login-btn');
  await page.waitForURL(/index\.html#\//, {timeout:30000});
  await page.waitForTimeout(3000);
  const out = await page.evaluate(async () => {
    const url = $.su.url('/admin/interface?form=status2');
    const variants = [];
    async function ajax(opts) { return new Promise(resolve => $.ajax(Object.assign({url, type:'POST', success:d=>resolve({ok:true,d}), error:x=>resolve({ok:false,status:x.status,text:x.responseText})}, opts))); }
    variants.push(['data-field-json', await ajax({data:{data: JSON.stringify({method:'get',params:{}})}})]);
    variants.push(['raw-json', await ajax({data:JSON.stringify({method:'get',params:{}}), contentType:'application/json'})]);
    variants.push(['data-field-opload', await ajax({data:{data: JSON.stringify({operation:'load'})}})]);
    variants.push(['data-field-opread', await ajax({data:{data: JSON.stringify({operation:'read'})}})]);
    const proxyOut = await new Promise(resolve => {
      const p = new $.su.Proxy({url, autoLoad:false});
      p.read({method:'get', params:{}}, d => resolve({ok:true,d}), x => resolve({ok:false,x}), x => resolve({fail:true,x}));
    });
    variants.push(['proxy-read', proxyOut]);
    return variants;
  });
  console.log(JSON.stringify(out, null, 2).slice(0,5000));
  await browser.close();
})();
