const { chromium } = require('playwright-core');
(async () => {
  const browser = await chromium.launch({executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: true, args:['--ignore-certificate-errors']});
  const page = await browser.newPage({ignoreHTTPSErrors: true});
  page.on('response', async res => {
    const url = res.url();
    if (url.includes('/cgi-bin/luci')) {
      let text = '';
      try { text = (await res.text()).slice(0, 500); } catch {}
      console.log('RESP', res.status(), url, text.replace(/\s+/g,' '));
    }
  });
  await page.goto('https://192.168.0.1/webpages/login.html', {waitUntil: 'networkidle', timeout: 30000});
  await page.locator('#login-username').fill('admin');
  const pass = page.locator('input[type="password"]:visible').first();
  console.log('visible pass count', await page.locator('input[type="password"]:visible').count());
  await pass.fill('@LS1805L1109@fk');
  await page.click('#login-btn');
  await page.waitForTimeout(8000);
  console.log('title', await page.title());
  console.log('url', page.url());
  console.log('bodyText', (await page.locator('body').innerText()).slice(0, 2000));
  console.log('cookies', await page.context().cookies());
  await page.screenshot({path:'tmp-er605-after-login2.png', fullPage:true});
  await browser.close();
})();
