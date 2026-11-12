import { expect, test } from '@playwright/test';
import { enterGame } from './helpers';

// David's cap: 64 player units plus two 64-unit NPC teams on screen at once. Units of one model and
// side share an instanced draw, so the draw count stays far below one per unit.
test('[PERF-01] 192 units on the map draw in well under one call per unit', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'phone', 'phone profile only');
  test.setTimeout(180_000);
  await enterGame(page);
  // Unit models stream in after the match starts; until then units share the placeholder tank.
  await expect
    .poll(async () => {
      const before = await page.evaluate(() => window.__TC_TEST__?.renderStats().loadedModels.length ?? 0);
      await page.waitForTimeout(1500);
      const after = await page.evaluate(() => window.__TC_TEST__?.renderStats().loadedModels.length ?? 0);
      return after > 1 && after === before;
    }, { timeout: 90_000 })
    .toBe(true);
  await page.evaluate(() => {
    window.__TC_TEST__?.freezeSim(600_000);
    const camera = window.__TC_TEST__?.camera();
    window.__TC_TEST__?.setCamera({ targetX: 0, targetZ: 0, distance: (camera?.distance ?? 40) * 1.8 });
  });
  const nextFrames = async () => {
    const frame = await page.evaluate(() => window.__TC_TEST__?.renderStats().frame ?? 0);
    await page.waitForFunction((start) => (window.__TC_TEST__?.renderStats().frame ?? 0) > start + 3, frame, { timeout: 120_000 });
  };
  await nextFrames();
  const empty = await page.evaluate(() => window.__TC_TEST__?.renderStats());
  const added = await page.evaluate(() => window.__TC_TEST__?.stressSpawn(64) ?? 0);
  expect(added).toBe(192);
  await nextFrames();
  const stats = await page.evaluate(() => window.__TC_TEST__?.renderStats());
  expect(stats?.units ?? 0).toBeGreaterThanOrEqual(192);
  expect(stats?.drawCalls ?? Infinity).toBeLessThan(120);
  // Zoomed out, units draw their low-detail models (budget about 2,500 triangles, 5,000 for big
  // units), not the full ones (3k to 10k): the 192 units add well under 4,000 triangles each.
  expect(stats?.lodUnits ?? 0).toBeGreaterThanOrEqual(150);
  const perUnit = ((stats?.triangles ?? Infinity) - (empty?.triangles ?? 0)) / added;
  expect(perUnit).toBeLessThan(4000);
});
