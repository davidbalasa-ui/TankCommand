// node clip.mjs <out.mp4> <query-string> [seconds=2.5] [fps=60]
// Renders the moving parts frame by frame (needs `npx vite tools/art/v2/viewer --port 5199` running).
import { chromium } from 'playwright';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
const [out, query, secs = '2.5', fps = '60'] = process.argv.slice(2);
const dir = mkdtempSync(join(tmpdir(), 'clip-'));
const browser = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader'] });
const page = await browser.newPage({ viewport: { width: 1280, height: 720 } });
page.on('pageerror', (e) => console.log('pageerror', e.message));
await page.goto(`http://localhost:5199/?${query}&w=1280&h=720`);
await page.waitForFunction(() => window.__ready && window.__ready(), null, { timeout: 120000 });
await page.waitForTimeout(1000);
const n = Math.round(Number(secs) * Number(fps));
for (let i = 0; i < n; i += 1) {
  await page.evaluate((t) => window.__setTime(t), i / Number(fps));
  await page.screenshot({ path: join(dir, `f${String(i).padStart(4, '0')}.png`) });
}
await browser.close();
execFileSync('ffmpeg', ['-loglevel', 'error', '-y', '-framerate', fps, '-i', join(dir, 'f%04d.png'), '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '20', out]);
rmSync(dir, { recursive: true });
console.log('wrote', out, n, 'frames');
