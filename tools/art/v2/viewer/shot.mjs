// node shot.mjs <out.png> <query-string>   (needs `npx vite tools/art/v2/viewer --port 5199` running)
import { chromium } from 'playwright';
const [out, query] = process.argv.slice(2);
const browser = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader'] });
const page = await browser.newPage({ viewport: { width: 1600, height: 900 } });
page.on('pageerror', (e) => console.log('pageerror', e.message));
await page.goto(`http://localhost:5199/?${query}`);
await page.waitForFunction(() => window.__ready && window.__ready(), null, { timeout: 120000 });
await page.waitForTimeout(1500);
await page.screenshot({ path: out });
await browser.close();
