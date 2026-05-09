const { chromium } = require('playwright');
const path = require('path');

(async () => {
  const browser = await chromium.launch();
  const context = await browser.newContext({
    viewport: { width: 1280, height: 720 },
    recordVideo: {
      dir: '/tmp/fortnite-video/',
      size: { width: 1280, height: 720 }
    }
  });
  const page = await context.newPage();

  const filePath = 'file://' + path.resolve(__dirname, 'fortnite.html');
  await page.goto(filePath);

  // Animation auto-plays 300ms after load + 26s of scenes + buffer
  await page.waitForTimeout(27000);

  await context.close();
  await browser.close();
  console.log('Video recorded.');
})();
