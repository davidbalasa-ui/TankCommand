// Captures Play Store screenshots (1920x1080) from the real game into store/.
// Needs a test-hook build being served:
//   VITE_TEST_HOOK=1 npm run build && npm run preview -- --host 127.0.0.1 --port 4255 --strictPort
// then: node tools/branding/screenshots.mjs   (optional: SHOT=battle to capture one)
import { mkdirSync } from 'node:fs';
import { resolve } from 'node:path';
import { chromium } from 'playwright';

const BASE = process.env.TC_URL ?? 'http://127.0.0.1:4255/';
const OUT = resolve(import.meta.dirname, '../../store');
mkdirSync(OUT, { recursive: true });
const only = process.env.SHOT;

const browser = await chromium.launch();

async function newPage(settings) {
  // 960x540 CSS pixels at 2x: phone-sized UI, 1920x1080 output.
  const page = await browser.newPage({ viewport: { width: 960, height: 540 }, deviceScaleFactor: 2 });
  page.setDefaultTimeout(30000);
  page.on('pageerror', (e) => console.error('page error:', e.message));
  await page.addInitScript((s) => {
    try {
      for (const [k, v] of Object.entries(s)) window.localStorage.setItem(k, v);
    } catch {
      // Storage may be unavailable.
    }
  }, settings);
  await page.goto(BASE);
  await page.waitForFunction(() => window.__TC_TEST__ !== undefined);
  // Full game unlocked so no lock badges sit on the content.
  await page.evaluate(() => window.__TC_TEST__.setFullGameUnlocked(true));
  return page;
}

const wait = (page, ms) => page.waitForTimeout(ms);

async function startSkirmish(page) {
  await page.getByRole('button', { name: 'Skirmish', exact: true }).click();
  await page.getByRole('button', { name: 'Start', exact: true }).click();
  await page.waitForFunction(() => window.__TC_TEST__?.screen() === 'inGame');
  await page.waitForFunction(() => (window.__TC_TEST__?.renderStats().frame ?? 0) > 0);
}

/** Two armies meeting in the middle of the map, with aircraft overhead. */
async function stageBattle(page) {
  return page.evaluate(() => {
    const h = window.__TC_TEST__;
    const pads = h.structures().filter((s) => s.kind === 'pad');
    const mine = pads.find((s) => s.owner === 1);
    const theirs = pads.find((s) => s.owner !== 1);
    const dx = theirs.x - mine.x;
    const dz = theirs.z - mine.z;
    const len = Math.hypot(dx, dz);
    const ux = dx / len;
    const uz = dz / len;
    // Off the centre line, clear of the ridge that crosses the middle of Cinder Basin.
    const mx = (mine.x + theirs.x) / 2 + uz * len * 0.22;
    const mz = (mine.z + theirs.z) / 2 - ux * len * 0.22;
    const heading = Math.atan2(dx, dz);
    const terran = ['unit.human.heavy_tank', 'unit.human.light_tank', 'unit.human.missile_tank', 'unit.human.heavy_tank', 'unit.human.hover_tank', 'unit.human.light_tank'];
    const arcadian = ['unit.alien.light_tank', 'unit.alien.light_skimmer', 'unit.alien.light_tank', 'unit.alien.saucer', 'unit.alien.light_skimmer', 'unit.alien.light_tank'];
    const ids = [];
    terran.forEach((t, i) => {
      const side = (i - 2.5) * 4;
      ids.push(h.spawnUnit(t, 1, mx - ux * (10 + (i % 2) * 4) - uz * side, mz - uz * (10 + (i % 2) * 4) + ux * side, heading));
    });
    arcadian.forEach((t, i) => {
      const side = (i - 2.5) * 4;
      h.spawnUnit(t, 2, mx + ux * (10 + (i % 2) * 4) - uz * side, mz + uz * (10 + (i % 2) * 4) + ux * side, heading + Math.PI);
    });
    h.spawnUnit('unit.human.fighter', 1, mx - ux * 4 - uz * 6, mz - uz * 4 + ux * 6, heading);
    h.spawnUnit('unit.human.bomber', 1, mx - ux * 6 + uz * 8, mz - uz * 6 - ux * 8, heading);
    h.spawnUnit('unit.alien.fighter', 2, mx + ux * 5 + uz * 4, mz + uz * 5 - ux * 4, heading + Math.PI);
    return { mx, mz, heading, ids };
  });
}

const shots = {
  async battle() {
    const page = await newPage({ 'setting.fog': 'revealed', 'setting.ai': 'normal', 'setting.gameSettings': '{"graphicsQuality":"high"}' });
    await startSkirmish(page);
    // Warm-up match: the first sight of a dozen unit types compiles their shaders in one long
    // frame, which the freeze watchdog reports. Stage once, then start a fresh match (which
    // clears the report) with everything already compiled.
    let s = await stageBattle(page);
    await page.evaluate((v) => window.__TC_TEST__.setCamera({ targetX: v.mx, targetZ: v.mz }), s);
    await wait(page, 9000);
    const after = await page.evaluate(() => window.__TC_TEST__.screen());
    if (process.env.DEBUG) console.log('warm-up ended on', after);
    if (after === 'recovery') {
      await page.getByRole('button', { name: 'Resume' }).click();
    }
    await page.waitForFunction(() => window.__TC_TEST__?.screen() === 'inGame');
    await page.locator('[data-control-id="inGame.pause"]').first().click();
    await page.locator('[data-control-id="pause.restart"]').first().click();
    await page.locator('[data-control-id="pause.confirmRestart"]').first().click();
    await page.waitForFunction(() => window.__TC_TEST__?.screen() === 'inGame');
    await wait(page, 1000);
    s = await stageBattle(page);
    await page.evaluate((v) => {
      const h = window.__TC_TEST__;
      h.autoplay(1, 'normal');
      const cam = h.camera();
      h.setCamera({ targetX: v.mx, targetZ: v.mz, distance: cam.distance * 0.95, yaw: v.heading + Math.PI / 2 + 0.5 });
      h.setSelection(v.ids.slice(0, 3));
    }, s);
    await wait(page, 4500);
    // The under-attack toast's red "!" reads as an error in a still image.
    await page.addStyleTag({ content: '.alert-toasts { display: none !important; }' });
    if ((await page.evaluate(() => window.__TC_TEST__.screen())) !== 'inGame') console.error('battle: not in game');
    await page.screenshot({ path: `${OUT}/screenshot-1-battle.png` });
    await page.close();
  },
  async build() {
    const page = await newPage({ 'setting.fog': 'revealed', 'setting.ai': 'off', 'setting.gameSettings': '{"graphicsQuality":"high"}' });
    await startSkirmish(page);
    const pt = await page.evaluate(() => {
      const h = window.__TC_TEST__;
      const pad = h.structures().find((s) => s.owner === 1 && s.kind === 'pad');
      h.setCamera({ targetX: pad.x, targetZ: pad.z });
      return { x: pad.x, z: pad.z };
    });
    await wait(page, 600);
    const p = await page.evaluate((v) => window.__TC_TEST__.worldToScreen(v.x, v.z), pt);
    await page.mouse.click(p.x, p.y);
    await wait(page, 1200);
    await page.screenshot({ path: `${OUT}/screenshot-2-build-menu.png` });
    await page.close();
  },
  async briefing() {
    const page = await newPage({});
    await page.getByRole('button', { name: /Campaign/ }).first().click();
    await page.locator('[data-control-id="campaignSelect.human"]').first().click();
    await page.locator('[data-control-id="missionSelect.mission"]').first().click();
    await page.waitForFunction(() => window.__TC_TEST__?.screen() === 'briefing');
    await wait(page, 1500);
    await page.screenshot({ path: `${OUT}/screenshot-3-briefing.png` });
    await page.close();
  },
  async skirmish() {
    const page = await newPage({});
    await page.getByRole('button', { name: 'Skirmish', exact: true }).click();
    await wait(page, 1500);
    await page.screenshot({ path: `${OUT}/screenshot-4-skirmish-setup.png` });
    await page.close();
  },
};

try {
  for (const [name, fn] of Object.entries(shots)) {
    if (only && name !== only) continue;
    await fn();
    console.log('captured', name);
  }
} finally {
  await browser.close();
}
