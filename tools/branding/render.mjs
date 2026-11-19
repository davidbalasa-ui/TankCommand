// Step 1 of the branding pipeline: render the hero models to transparent PNGs.
// Usage (repo root, after npm ci): node tools/branding/render.mjs [outDir]
// Then run: python3 tools/branding/compose.py
// Serves the repo root on a local port, opens tools/branding/scene.html in headless Chromium
// and saves one PNG per shot listed below (default outDir: tools/branding/build).
import { createServer } from 'node:http';
import { mkdirSync, readFileSync, writeFileSync, existsSync, statSync } from 'node:fs';
import { extname, join, resolve } from 'node:path';
import { chromium } from 'playwright';

const root = resolve(import.meta.dirname, '../..');
const outDir = resolve(process.argv[2] ?? join(root, 'tools/branding/build'));
mkdirSync(outDir, { recursive: true });

export const SHOTS = [
  // Terran heavy tank, 3/4 front view: the icon, splash and feature graphic hero.
  { name: 'terran_hero', url: '/public/assets/models/human/bulwark.glb', size: 1536, yaw: -1.0, pitch: 0.42, fill: 0.95, exposure: 1.5, rimI: 7 },
  // Same tank turned further toward the camera and lit brighter: compact silhouette for the icons.
  { name: 'terran_icon', url: '/public/assets/models/human/bulwark.glb', size: 1536, yaw: -1.12, pitch: 0.5, fill: 0.95, exposure: 1.9, rimI: 8 },
  // Arcadian heavy hover tank, facing the other way, warm gold rim: feature graphic opponent.
  {
    name: 'arcadian_hero',
    url: '/public/assets/models/alien/carapace.glb',
    size: 1536,
    yaw: -2.2,
    exposure: 1.3,
    pitch: 0.3,
    rim: '#ffcf6a',
    accent: '#ffe7a8',
    fill: 0.95,
  },
];

const TYPES = { '.html': 'text/html', '.js': 'text/javascript', '.glb': 'model/gltf-binary', '.png': 'image/png' };
const server = createServer((req, res) => {
  const path = join(root, decodeURIComponent(new URL(req.url, 'http://x').pathname));
  if (!path.startsWith(root) || !existsSync(path) || statSync(path).isDirectory()) {
    res.writeHead(404).end();
    return;
  }
  res.writeHead(200, { 'content-type': TYPES[extname(path)] ?? 'application/octet-stream' });
  res.end(readFileSync(path));
});
await new Promise((ok) => server.listen(0, '127.0.0.1', ok));
const port = server.address().port;

const only = process.env.SHOT;
const browser = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
try {
  const page = await browser.newPage();
  page.on('pageerror', (e) => console.error('page error:', e.message));
  await page.goto(`http://127.0.0.1:${port}/tools/branding/scene.html`);
  await page.waitForFunction(() => window.sceneReady === true);
  for (const shot of SHOTS) {
    if (only && shot.name !== only) continue;
    const data = await page.evaluate((o) => window.renderModel(o), shot);
    const file = join(outDir, `${shot.name}.png`);
    writeFileSync(file, Buffer.from(data.split(',')[1], 'base64'));
    console.log('rendered', file);
  }
} finally {
  await browser.close();
  server.close();
}
