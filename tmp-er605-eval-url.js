const { chromium } = require('playwright-core');
(async () => {
  const browser = await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe', headless:true, args:['--ignore-certificate-errors']});
  const page = await browser.newPage({ignoreHTTPSErrors:true});
  await page.goto('https://192.168.0.1/webpages/login.html', {waitUntil:'networkidle', timeout:30000});
  await page.locator('#login-username').fill('admin');
  await page.locator('input[type="password"]:visible').first().fill('@LS1805L1109@fk');
  await page.click('#login-btn');
  await page.waitForURL(/index\.html#\//, {timeout:30000});
  await page.waitForTimeout(5000);
  const info = await page.evaluate(() => ({token: localStorage.getItem('token'), suUrl: $.su.url('/admin/interface?form=status2'), suUrlNat: $.su.url('/admin/nat?form=vs'), href: location.href}));
  console.log(JSON.stringify(info, null, 2));
  const res = await page.evaluate(() => new Promise(resolve => {
    $.ajax({url: $.su.url('/admin/interface?form=status2'), type:'GET', success: d => resolve({ok:true,d}), error: x => resolve({ok:false,status:x.status,text:x.responseText})});
  }));
  console.log('ajax', JSON.stringify(res).slice(0,1000));
  const nat = await page.evaluate(() => new Promise(resolve => {
    $.ajax({url: $.su.url('/admin/nat?form=vs'), type:'GET', success: d => resolve({ok:true,d}), error: x => resolve({ok:false,status:x.status,text:x.responseText})});
  }));
  console.log('nat ajax', JSON.stringify(nat).slice(0,1000));
  await browser.close();
})();
