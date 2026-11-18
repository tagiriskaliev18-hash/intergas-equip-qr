const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const outDir = 'C:\\Users\\user\\.gemini\\antigravity\\brain\\6e645d09-68bf-406f-819a-9a30a9bd4c94';
fs.mkdirSync(outDir, { recursive: true });

async function run() {
  const browser = await chromium.launch({
    headless: true,
    args: ['--ignore-certificate-errors']
  });

  // Desktop Context (1440x900)
  const deskContext = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    ignoreHTTPSErrors: true
  });
  const deskPage = await deskContext.newPage();

  console.log('Navigating to Desktop https://127.0.0.1:8443...');
  await deskPage.goto('https://127.0.0.1:8443', { waitUntil: 'networkidle' });
  await deskPage.screenshot({ path: path.resolve(outDir, 'contact_desktop_1440.png') });
  console.log('Captured contact_desktop_1440.png');

  // Switch to Plan tab on Desktop
  await deskPage.click('#tab-btn-budget');
  await deskPage.waitForTimeout(400);
  await deskPage.screenshot({ path: path.resolve(outDir, 'plan_desktop_1440.png') });
  console.log('Captured plan_desktop_1440.png');

  // Login page Desktop
  await deskPage.goto('https://127.0.0.1:8443/auth/login', { waitUntil: 'networkidle' });
  await deskPage.screenshot({ path: path.resolve(outDir, 'login_desktop_1440.png') });
  console.log('Captured login_desktop_1440.png');

  deskPage.on('console', msg => console.log('DESK LOG:', msg.text()));
  deskPage.on('pageerror', err => console.log('DESK ERROR:', err));

  // Equipment Page Desktop
  await deskPage.goto('https://127.0.0.1:8443/doc/ks-gpa-16-ural', { waitUntil: 'networkidle' });
  await deskPage.waitForTimeout(1000);
  await deskPage.screenshot({ path: path.resolve(outDir, 'equipment_desktop_1440.png') });
  console.log('Captured equipment_desktop_1440.png');

  // Switch to Maintenance & ZIP tab in Equipment Desktop
  await deskPage.click('#tab-btn-maint');
  await deskPage.waitForTimeout(600);
  await deskPage.screenshot({ path: path.resolve(outDir, 'equipment_maint_desktop_1440.png') });
  console.log('Captured equipment_maint_desktop_1440.png');

  // Mobile Context (iPhone 14/15/16: 390x844)
  const mobContext = await browser.newContext({
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 2,
    isMobile: true,
    hasTouch: true,
    ignoreHTTPSErrors: true
  });
  const mobPage = await mobContext.newPage();

  console.log('Navigating to Mobile https://127.0.0.1:8443...');
  await mobPage.goto('https://127.0.0.1:8443', { waitUntil: 'networkidle' });
  await mobPage.screenshot({ path: path.resolve(outDir, 'contact_iphone_390.png') });
  console.log('Captured contact_iphone_390.png');

  // Switch to Plan tab on Mobile
  await mobPage.click('#tab-btn-budget');
  await mobPage.waitForTimeout(400);
  await mobPage.screenshot({ path: path.resolve(outDir, 'plan_iphone_390.png') });
  console.log('Captured plan_iphone_390.png');

  await mobPage.goto('https://127.0.0.1:8443/doc/ks-gpa-16-ural', { waitUntil: 'networkidle' });
  await mobPage.waitForTimeout(1000);
  await mobPage.screenshot({ path: path.resolve(outDir, 'equipment_iphone_390.png') });
  console.log('Captured equipment_iphone_390.png');

  // Switch to Maintenance & ZIP tab in Equipment Mobile
  await mobPage.click('#tab-btn-maint');
  await mobPage.waitForTimeout(600);
  await mobPage.screenshot({ path: path.resolve(outDir, 'equipment_maint_iphone_390.png') });
  console.log('Captured equipment_maint_iphone_390.png');

  await browser.close();
  console.log('Visual audit capture complete!');
}

run().catch(err => {
  console.error('Audit failed:', err);
  process.exit(1);
});
