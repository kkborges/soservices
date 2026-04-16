const { chromium } = require('playwright-core');
(async () => {
  const browser = await chromium.launch({executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: true, args:['--ignore-certificate-errors']});
  const page = await browser.newPage({ignoreHTTPSErrors: true});
  page.on('console', msg => console.log('CONSOLE', msg.type(), msg.text()));
  page.on('response', res => { if (res.url().includes('cgi') || res.url().includes('ds') || res.url().includes('login')) console.log('RESP', res.status(), res.url()); });
  await page.goto('https://192.168.0.1/webpages/login.html', {waitUntil: 'networkidle', timeout: 30000});
  console.log('title', await page.title());
  console.log('url', page.url());
  console.log('inputs', await page.locator('input').evaluateAll(xs => xs.map(x => ({id:x.id,name:x.name,type:x.type,value:x.value,placeholder:x.getAttribute('placeholder')}))));
  console.log('buttons', await page.locator('button').evaluateAll(xs => xs.map(x => ({id:x.id,text:x.innerText,type:x.type}))));
  await page.screenshot({path:'tmp-er605-login.png', fullPage:true});
  await browser.close();
})();
