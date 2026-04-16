const { chromium } = require('playwright-core');
(async () => {
  const browser = await chromium.launch({executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: true, args:['--ignore-certificate-errors']});
  const page = await browser.newPage({ignoreHTTPSErrors: true});
  page.on('response', async res => {
    const url = res.url();
    if (url.includes('/cgi-bin/luci')) {
      let text = '';
      try { text = (await res.text()).slice(0, 300); } catch {}
      console.log('RESP', res.status(), url, text.replace(/\s+/g,' '));
    }
  });
  await page.goto('https://192.168.0.1/webpages/login.html', {waitUntil: 'networkidle', timeout: 30000});
  await page.fill('#login-username', 'admin');
  await page.fill('#login-password', '@LS1805L1109@fk');
  await Promise.all([
    page.waitForLoadState('networkidle', {timeout: 30000}).catch(()=>{}),
    page.click('#login-btn')
  ]);
  await page.waitForTimeout(5000);
  console.log('title', await page.title());
  console.log('url', page.url());
  console.log('bodyText', (await page.locator('body').innerText()).slice(0, 1200));
  console.log('localStorage', await page.evaluate(() => Object.fromEntries(Object.entries(localStorage))));
  console.log('cookies', await page.context().cookies());
  await page.screenshot({path:'tmp-er605-after-login.png', fullPage:true});
  await browser.close();
})();
