import { expect, test } from '@playwright/test';
import { enterGame } from './helpers';

test('[FOG-05] with fog on a hidden enemy is not listed, drawn or pickable; revealed shows it', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'phone', 'phone-only touch flow');
  await enterGame(page, { fog: true });
  await page.screenshot({ path: 'test-results/shots/wp06-1-fog-at-start.png' });
  const enemies = await page.evaluate(
    () => window.__TC_TEST__?.units().filter((unit) => unit.owner !== 1).length ?? -1,
  );
  expect(enemies).toBe(0);
  const meshes = await page.evaluate(() => window.__TC_TEST__?.hud()?.enemyUnits ?? -1);
  expect(meshes).toBe(0);
  const drawn = await page.evaluate(() => ({
    drawn: window.__TC_TEST__?.renderStats().units ?? -1,
    listed: window.__TC_TEST__?.units().length ?? -2,
  }));
  expect(drawn.drawn).toBe(drawn.listed);
  const hiddenIds = await page.evaluate(() => {
    const hook = window.__TC_TEST__;
    let found = 0;
    for (let id = 1; id < 80; id += 1) {
      const own = hook?.units().some((unit) => unit.id === id) ?? false;
      if (!own && hook?.unitScreenCentre(id)) {
        found += 1;
      }
    }
    return found;
  });
  expect(hiddenIds).toBe(0);
});

test('[FOG-05] revealed mode shows enemies', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'phone', 'phone-only touch flow');
  await enterGame(page, { fog: false });
  await expect
    .poll(async () => page.evaluate(() => window.__TC_TEST__?.units().filter((unit) => unit.owner !== 1).length ?? 0))
    .toBeGreaterThan(0);
});
