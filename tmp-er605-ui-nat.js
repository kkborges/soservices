const { chromium } = require('playwright-core');
(async () => {
  const browser = await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe', headless:true, args:['--ignore-certificate-errors']});
  const page = await browser.newPage({ignoreHTTPSErrors:true});
  page.on('response', async res => {
    const u=res.url();
    if (u.includes('/admin/nat') || u.includes('/admin/upnp') || u.includes('/userconfig')) {
      let txt=''; try{txt=(await res.text()).slice(0,700).replace(/\s+/g,' ')}catch{}
      console.log('RESP', res.status(), u, txt);
    }
  });
  await page.goto('https://192.168.0.1/webpages/login.html', {waitUntil:'networkidle', timeout:30000});
  await page.locator('#login-username').fill('admin');
  await page.locator('input[type="password"]:visible').first().fill('@LS1805L1109@fk');
  await page.click('#login-btn');
  await page.waitForURL(/index\.html#\//, {timeout:30000});
  await page.waitForTimeout(4000);
  console.log('body initial', (await page.locator('body').innerText()).slice(0,1000));
  for (const text of ['Transmission','NAT','Virtual Servers','Virtual Server']) {
    const loc = page.getByText(text, {exact:false}).first();
    console.log('try click', text, await loc.count());
    try { await loc.click({timeout:5000}); await page.waitForTimeout(2500); } catch(e) { console.log('click failed', text, e.message.slice(0,200)); }
  }
  console.log('url', page.url());
  console.log('body final', (await page.locator('body').innerText()).slice(0,3000));
  await page.screenshot({path:'tmp-er605-virtual-server.png', fullPage:true});
  await browser.close();
})();
