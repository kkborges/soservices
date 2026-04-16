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
  const endpoints = ['/admin/nat?form=setting','/admin/nat?form=vs','/admin/nat?form=pt','/admin/nat?form=dmz','/admin/upnp?form=enable','/admin/nat?form=alg'];
  const out = await page.evaluate(async endpoints => {
    async function read(url) { return new Promise(resolve => { const p = new $.su.Proxy({url: $.su.url(url), autoLoad:false}); p.read({method:'get', params:{}}, d => resolve({ok:true,d}), x => resolve({ok:false,x}), x => resolve({fail:true,x})); }); }
    const data = {};
    for (const ep of endpoints) data[ep] = await read(ep);
    return data;
  }, endpoints);
  console.log(JSON.stringify(out, null, 2));
  await browser.close();
})();
