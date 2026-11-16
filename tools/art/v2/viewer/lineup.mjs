// node lineup.mjs <out.png> <query-string>: 2x screenshot plus a .pos file with each model's label anchor (screen fractions).
import { chromium } from 'playwright';
import fs from 'fs';
const [out, query] = process.argv.slice(2);
const browser = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader'] });
const page = await browser.newPage({ viewport: { width: Number(process.argv[4] || 1600), height: Number(process.argv[5] || 900) }, deviceScaleFactor: 1 });
page.on('pageerror', (e) => console.log('pageerror', e.message));
await page.goto(`http://localhost:5199/?${query}`);
await page.waitForFunction(() => window.__ready && window.__ready(), null, { timeout: 180000 });
await page.waitForTimeout(2500);
const pos = await page.evaluate(() => window.__anchors());
fs.writeFileSync(out + '.pos', pos.join(' '));
await page.screenshot({ path: out });
await browser.close();
