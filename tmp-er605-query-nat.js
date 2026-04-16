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
  const stok = await page.evaluate(() => localStorage.getItem('token'));
  console.log('stok', stok);
  const endpoints = ['/admin/nat?form=setting','/admin/nat?form=vs','/admin/nat?form=pt','/admin/nat?form=dmz','/admin/upnp?form=enable','/admin/interface?form=status2'];
  for (const ep of endpoints) {
    const url = `https://192.168.0.1/cgi-bin/luci/;stok=${stok}${ep}`;
    const res = await page.request.post(url, {data:{id:1, method:'get', params:{}}});
    const text = await res.text();
    console.log('POST', ep, res.status(), text.slice(0,1000).replace(/\s+/g,' '));
    const res2 = await page.request.get(url);
    const text2 = await res2.text();
    console.log('GET', ep, res2.status(), text2.slice(0,500).replace(/\s+/g,' '));
  }
  await browser.close();
})();
