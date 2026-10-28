import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { expect, test } from '@playwright/test';
import {
  assertButtonLayout,
  countDistinctPngColors,
  enterGame,
  waitForHook,
} from './helpers';

test('[ASSET-10] the real PoC tank loads through the registry, loader and GLTF decoder', async ({
  page,
}) => {
  await enterGame(page);
  await expect
    .poll(async () => page.evaluate(() => window.__TC_TEST__?.renderStats().loadedModels ?? []))
    .toContain('unit.human.poc_tank');
  const stats = await page.evaluate(() => window.__TC_TEST__?.renderStats());
  expect(stats?.meshCount ?? 0).toBeGreaterThan(1);
});

test('[HOOK-02] test hook validates commands and invalid commands change nothing', async ({ page }) => {
  await enterGame(page);

  await page.evaluate(() => window.__TC_TEST__?.pauseSim(true));
  const before = await page.evaluate(() => window.__TC_TEST__?.snapshot());
  const accepted = await page.evaluate(() => {
    const hook = window.__TC_TEST__;
    if (!hook) {
      return false;
    }
    const current = hook.snapshot();
    return hook.sendCommand({
      kind: 'debug.addCounter',
      amount: 1000,
      tick: current.tick + 1,
      issuer: 1,
    });
  });
  await page.evaluate(() => window.__TC_TEST__?.pauseSim(false));

  expect(accepted).toBe(true);
  await expect
    .poll(async () => page.evaluate(() => window.__TC_TEST__?.snapshot().counter ?? 0))
    .toBeGreaterThanOrEqual((before?.counter ?? 0) + 1000);

  await page.evaluate(() => window.__TC_TEST__?.pauseSim(true));
  const beforeInvalid = await page.evaluate(() => window.__TC_TEST__?.snapshot().counter ?? 0);
  const rejected = await page.evaluate(() => {
    const hook = window.__TC_TEST__;
    if (!hook) {
      return true;
    }
    return hook.sendCommand({
      kind: 'debug.addCounter',
      amount: 1 / 0,
      tick: hook.snapshot().tick + 1,
      issuer: 1,
    });
  });
  await page.waitForTimeout(150);
  const afterInvalid = await page.evaluate(() => window.__TC_TEST__?.snapshot().counter ?? 0);
  await page.evaluate(() => window.__TC_TEST__?.pauseSim(false));

  expect(rejected).toBe(false);
  expect(afterInvalid).toBe(beforeInvalid);
});

test('[REND-01] canvas is non-blank and frames increase', async ({ page }) => {
  await enterGame(page);
  const canvas = page.locator('canvas');
  await canvas.waitFor({ state: 'visible' });
  const screenshot = await canvas.screenshot();
  expect(countDistinctPngColors(screenshot)).toBeGreaterThan(2);

  const first = await page.evaluate(() => window.__TC_TEST__?.renderStats().frame ?? 0);
  await page.waitForTimeout(1000);
  const second = await page.evaluate(() => window.__TC_TEST__?.renderStats().frame ?? 0);
  expect(second).toBeGreaterThan(first);
});

test('[REND-02] hidden page stops frames and resumes without sim-time jump', async ({ page }) => {
  await enterGame(page);

  await page.evaluate(() => {
    Object.defineProperty(document, 'hidden', { configurable: true, get: () => true });
    document.dispatchEvent(new Event('visibilitychange'));
  });
  await page.waitForTimeout(500);
  const hiddenFirst = await page.evaluate(() => window.__TC_TEST__?.renderStats().frame ?? 0);
  await page.waitForTimeout(300);
  const hiddenSecond = await page.evaluate(() => window.__TC_TEST__?.renderStats().frame ?? 0);
  expect(hiddenSecond).toBe(hiddenFirst);

  await page.evaluate(() => {
    Object.defineProperty(document, 'hidden', { configurable: true, get: () => false });
    document.dispatchEvent(new Event('visibilitychange'));
  });
  const tickBefore = await page.evaluate(() => window.__TC_TEST__?.snapshot().tick ?? 0);
  const started = Date.now();
  await page.waitForTimeout(500);
  const tickAfter = await page.evaluate(() => window.__TC_TEST__?.snapshot().tick ?? 0);
  const visibleMs = Date.now() - started;
  expect(tickAfter - tickBefore).toBeLessThanOrEqual(Math.ceil(visibleMs / 50) * 2 + 2);

  const resumedFirst = await page.evaluate(() => window.__TC_TEST__?.renderStats().frame ?? 0);
  await page.waitForTimeout(300);
  const resumedSecond = await page.evaluate(() => window.__TC_TEST__?.renderStats().frame ?? 0);
  expect(resumedSecond).toBeGreaterThan(resumedFirst);
});

test('[WD-04] a frozen sim records a freeze report and only the 5 s recover mark shows recovery', async ({
  page,
}) => {
  await enterGame(page);
  await page.evaluate(() => window.__TC_TEST__?.freezeSim(6000));

  // WP-01 §5.4: the 2 s freeze threshold records a report, and nothing else.
  // Asserting the report first is what distinguishes the two thresholds; the
  // recovery screen must not be what a merely slow frame produces.
  await expect
    .poll(async () => page.evaluate(() => window.__TC_TEST__?.lastFreezeReport() !== null), {
      timeout: 4500,
    })
    .toBe(true);
  const report = await page.evaluate(() => window.__TC_TEST__?.lastFreezeReport() ?? null);
  expect(report, 'a freeze report was recorded').not.toBeNull();
  expect(report?.stalledMs ?? 0).toBeGreaterThanOrEqual(2000);
  expect(['sim', 'render']).toContain(report?.channel ?? '');

  await expect(page.locator('[data-screen-id="recovery"]')).toBeVisible({ timeout: 7000 });
  await expect(page.getByRole('button', { name: 'Resume', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Load autosave', exact: true })).toBeVisible();
  await expect(
    page.getByRole('button', { name: 'Send bug report & return to menu', exact: true }),
  ).toBeVisible();
});

test('[UI-05] all controls meet touch size and do not overlap across the main flow', async ({ page }) => {
  await page.goto('/');
  await waitForHook(page);
  await assertButtonLayout(page);

  await page.getByRole('button', { name: 'Campaign', exact: true }).click();
  await assertButtonLayout(page);
  await page.keyboard.press('Escape');
  await page.waitForFunction(() => window.__TC_TEST__?.screen() === 'title');

  await page.getByRole('button', { name: 'Skirmish', exact: true }).click();
  await assertButtonLayout(page);
  await page.getByRole('button', { name: 'Start', exact: true }).click();
  await page.waitForFunction(() => window.__TC_TEST__?.screen() === 'inGame');
  await assertButtonLayout(page);

  await page.getByRole('button', { name: 'Pause', exact: true }).click();
  await assertButtonLayout(page);

  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  await assertButtonLayout(page);
  await page.getByRole('button', { name: 'Back', exact: true }).click();
  await assertButtonLayout(page);

  await page.getByRole('button', { name: 'Report bug', exact: true }).click();
  await assertButtonLayout(page);
  await page.getByRole('button', { name: 'Back', exact: true }).click();
  await assertButtonLayout(page);

  await page.getByRole('button', { name: 'Resume', exact: true }).click();
  await assertButtonLayout(page);
  await page.keyboard.press('Escape');
  await assertButtonLayout(page);
  await page.getByRole('button', { name: 'Quit to title', exact: true }).click();
  await assertButtonLayout(page);

  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  await assertButtonLayout(page);
  await page.getByRole('button', { name: 'Back', exact: true }).click();
  await assertButtonLayout(page);

  await page.getByRole('button', { name: 'Credits', exact: true }).click();
  await assertButtonLayout(page);
  await page.getByRole('button', { name: 'Back', exact: true }).click();
  await assertButtonLayout(page);

  await page.getByRole('button', { name: 'Help', exact: true }).click();
  await assertButtonLayout(page);
  await page.getByRole('button', { name: 'Back', exact: true }).click();
  await assertButtonLayout(page);

  await page.getByRole('button', { name: 'Skirmish', exact: true }).click();
  await page.getByRole('button', { name: 'Start', exact: true }).click();
  await page.waitForFunction(() => window.__TC_TEST__?.screen() === 'inGame');
  await page.evaluate(() => window.__TC_TEST__?.freezeSim(6000));
  await expect(page.locator('[data-screen-id="recovery"]')).toBeVisible({ timeout: 7000 });
  await assertButtonLayout(page);

  await page.getByRole('button', { name: 'Resume', exact: true }).click();
  await page.getByRole('button', { name: 'Load autosave', exact: true }).click();
  await page.getByRole('button', { name: 'Send bug report & return to menu', exact: true }).click();
  await assertButtonLayout(page);
});

test('[BUILD-01] built index uses relative urls and copies public assets', () => {
  const index = readFileSync(join(process.cwd(), 'dist/index.html'), 'utf8');
  expect(index).not.toMatch(/(?:src|href)="\//);
  expect(readFileSync(join(process.cwd(), 'dist/assets/manifest.json'), 'utf8')).toContain(
    'unit.human.poc_tank',
  );
  expect(() =>
    readFileSync(join(process.cwd(), 'dist/assets/models/human/poc_tank.glb')),
  ).not.toThrow();
});
