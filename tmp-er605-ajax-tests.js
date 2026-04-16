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
  const tests = [
    {name:'vs load', url:'/admin/nat?form=vs', data:{operation:'load'}},
    {name:'vs read', url:'/admin/nat?form=vs', data:{operation:'read'}},
    {name:'vs get', url:'/admin/nat?form=vs', data:{method:'get',params:{}}},
    {name:'setting read', url:'/admin/nat?form=setting', data:{operation:'read'}},
    {name:'setting get', url:'/admin/nat?form=setting', data:{method:'get',params:{}}},
    {name:'iface read', url:'/admin/interface?form=status2', data:{operation:'read'}},
    {name:'iface get', url:'/admin/interface?form=status2', data:{method:'get',params:{}}},
  ];
  for (const t of tests) {
    const out = await page.evaluate(async (t) => new Promise(resolve => {
      $.ajax({url: $.su.url(t.url), type:'POST', data:t.data, success: d => resolve({ok:true,d}), error: x => resolve({ok:false,status:x.status,text:x.responseText})});
    }), t);
    console.log(t.name, JSON.stringify(out).slice(0,1200));
  }
  await browser.close();
})();
