import { mkdirSync } from 'node:fs';
import { join } from 'node:path';
import { expect, test, type Page } from '@playwright/test';
import { enterGame } from './helpers';

const PHONE_ONLY = 'screens are captured on the phone project only';

mkdirSync(join(process.cwd(), 'test-results', 'shots'), { recursive: true });

async function waitFrames(page: Page, minFrames: number): Promise<void> {
  const start = await page.evaluate(() => window.__TC_TEST__?.renderStats().frame ?? 0);
  await expect
    .poll(async () => {
      const current = await page.evaluate(() => window.__TC_TEST__?.renderStats().frame ?? 0);
      return current - start;
    })
    .toBeGreaterThanOrEqual(minFrames);
}

test('[screens] wp03-1-battle-default', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'phone', PHONE_ONLY);
  await enterGame(page);
  await expect
    .poll(async () => page.evaluate(() => window.__TC_TEST__?.renderStats().loadedModels ?? []))
    .toContain('unit.human.poc_tank');
  await waitFrames(page, 3);
  await page.screenshot({ path: 'test-results/shots/wp03-1-battle-default.png' });
});

test('[screens] wp03-2-zoomed-out-full-map', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'phone', PHONE_ONLY);
  await enterGame(page);
  await page.evaluate(() => window.__TC_TEST__?.setCamera({ targetX: 0, targetZ: 0, distance: 100000 }));
  await waitFrames(page, 3);
  await page.screenshot({ path: 'test-results/shots/wp03-2-zoomed-out-full-map.png' });
});

test('[screens] wp03-3-units-selected-command-bar', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'phone', PHONE_ONLY);
  await enterGame(page);
  const ids = await page.evaluate(() => {
    const hook = window.__TC_TEST__;
    if (!hook) return [];
    return hook.units().filter((u) => u.owner === 1).map((u) => u.id);
  });
  await page.evaluate((selection) => window.__TC_TEST__?.setSelection(selection), ids);
  await expect
    .poll(async () => page.evaluate(() => window.__TC_TEST__?.hud()?.selectedCount ?? 0))
    .toBe(ids.length);
  await waitFrames(page, 3);
  await page.screenshot({ path: 'test-results/shots/wp03-3-units-selected-command-bar.png' });
});

test('[screens] wp03-4-groups-open', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'phone', PHONE_ONLY);
  await enterGame(page);
  // The whole command bar is disabled with no selection, so pick something
  // first so the Groups button is enabled and the strip can be opened.
  const ids = await page.evaluate(() => {
    const hook = window.__TC_TEST__;
    if (!hook) return [];
    return hook.units().filter((u) => u.owner === 1).map((u) => u.id);
  });
  await page.evaluate((selection) => window.__TC_TEST__?.setSelection(selection), ids);
  await expect
    .poll(async () =>
      page.evaluate(
        () => document.querySelector<HTMLButtonElement>('[data-control-id="inGame.groups"]')?.disabled ?? true,
      ),
    )
    .toBe(false);
  await page.evaluate(() => {
    document.querySelector<HTMLButtonElement>('[data-control-id="inGame.groups"]')?.click();
  });
  await expect
    .poll(async () => page.evaluate(() => window.__TC_TEST__?.hud()?.groupsOpen ?? false))
    .toBe(true);
  await waitFrames(page, 3);
  await page.screenshot({ path: 'test-results/shots/wp03-4-groups-open.png' });
});

test('[screens] wp03-5-left-handed', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'phone', PHONE_ONLY);
  await enterGame(page);
  await page.evaluate(() => {
    document.querySelector<HTMLButtonElement>('[data-control-id="inGame.leftHanded"]')?.click();
  });
  await expect
    .poll(async () => page.evaluate(() => window.__TC_TEST__?.hud()?.leftHanded ?? false))
    .toBe(true);
  await waitFrames(page, 3);
  await page.screenshot({ path: 'test-results/shots/wp03-5-left-handed.png' });
});
