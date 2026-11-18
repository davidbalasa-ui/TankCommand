import { expect, test, type Page, type TestInfo } from '@playwright/test';
import { enterGame, gotoQuiet, waitForHook } from './helpers';

function requirePhone(testInfo: TestInfo): void {
  test.skip(testInfo.project.name !== 'phone', 'phone-first save / pause flow');
}

async function tap(page: Page, controlId: string): Promise<void> {
  await page.locator(`[data-control-id="${controlId}"]`).first().tap();
}

async function waitScreen(page: Page, screen: string): Promise<void> {
  await expect.poll(async () => page.evaluate(() => window.__TC_TEST__?.screen() ?? '')).toBe(screen);
}

async function counter(page: Page): Promise<number> {
  return page.evaluate(() => window.__TC_TEST__?.snapshot().counter ?? 0);
}

test('[SAVE-06] a manual save loads from the title screen, and deleting a slot asks first', async ({ page }, testInfo) => {
  requirePhone(testInfo);
  await enterGame(page);
  // Brand the match so the loaded game is told apart from a fresh one.
  const marker = 40_000;
  await page.evaluate((amount) => {
    const hook = window.__TC_TEST__;
    hook?.sendCommand({ kind: 'debug.addCounter', amount, tick: (hook.snapshot().tick ?? 0) + 1, issuer: 1 });
  }, marker);
  await expect.poll(async () => counter(page)).toBeGreaterThanOrEqual(marker);

  await tap(page, 'inGame.pause');
  await waitScreen(page, 'pause');
  await tap(page, 'pause.save');
  await waitScreen(page, 'saveSlots');
  await tap(page, 'saveSlots.save2');
  await expect.poll(async () => page.evaluate(() => window.__TC_TEST__?.lastSaveOutcome()?.status ?? '')).toBe('ok');
  await expect(page.locator('[data-slot="manual-2"] .save-title')).toHaveText('Skirmish');
  await tap(page, 'saveSlots.back');
  await waitScreen(page, 'pause');
  await tap(page, 'pause.quit');
  await tap(page, 'pause.confirmQuit');
  await waitScreen(page, 'title');

  // A fresh launch: the title screen opens the saved games.
  await page.reload();
  await waitForHook(page);
  await tap(page, 'title.load');
  await waitScreen(page, 'saveSlots');
  // Nothing to save from the title: a slot offers Load and Delete only.
  await expect(page.locator('[data-control-id="saveSlots.save1"]')).toHaveCount(0);
  await expect(page.locator('[data-slot="manual-2"] .save-title')).toHaveText('Skirmish');
  await expect(page.locator('[data-slot="manual-2"] .save-detail')).toContainText('played');
  await expect(page.locator('[data-control-id="saveSlots.load1"]')).toBeDisabled();
  await page.screenshot({ path: 'test-results/shots/saves-1-title-load.png' });

  // Delete asks first; Cancel keeps the save.
  await tap(page, 'saveSlots.delete2');
  await expect(page.locator('[data-control-id="saveSlots.confirmDelete"]')).toBeVisible();
  await page.screenshot({ path: 'test-results/shots/saves-2-delete-confirm.png' });
  await tap(page, 'saveSlots.cancelConfirm');
  await expect(page.locator('[data-control-id="saveSlots.confirmDelete"]')).toHaveCount(0);
  await expect(page.locator('[data-slot="manual-2"] .save-title')).toHaveText('Skirmish');

  await tap(page, 'saveSlots.load2');
  await waitScreen(page, 'inGame');
  await expect.poll(async () => counter(page)).toBeGreaterThanOrEqual(marker);

  // Back to the slots from the match: delete it for real.
  await tap(page, 'inGame.pause');
  await waitScreen(page, 'pause');
  await tap(page, 'pause.load');
  await waitScreen(page, 'saveSlots');
  await tap(page, 'saveSlots.delete2');
  await tap(page, 'saveSlots.confirmDelete');
  await expect(page.locator('[data-slot="manual-2"] .save-title')).toHaveText('Empty');
  await expect(page.locator('[data-control-id="saveSlots.load2"]')).toBeDisabled();
  expect(await page.evaluate(async () => (await window.__TC_TEST__?.listSaveSlots())?.find((s) => s.slot === 'manual-2')?.status)).toBe('missing');
});

test('[GAME-01] the pause menu offers help and a confirmed restart', async ({ page }, testInfo) => {
  requirePhone(testInfo);
  await enterGame(page);
  await page.evaluate(() => window.__TC_TEST__?.setSimSpeed(4));
  await expect.poll(async () => page.evaluate(() => window.__TC_TEST__?.snapshot().tick ?? 0)).toBeGreaterThan(200);
  await tap(page, 'inGame.pause');
  await waitScreen(page, 'pause');
  // Objectives belong to campaign missions only.
  await expect(page.locator('[data-control-id="pause.objectives"]')).toHaveCount(0);
  await page.screenshot({ path: 'test-results/shots/saves-3-pause.png' });

  await tap(page, 'pause.help');
  await waitScreen(page, 'help');
  await tap(page, 'help.back');
  await waitScreen(page, 'pause');

  await tap(page, 'pause.restart');
  await expect(page.locator('[data-control-id="pause.confirmRestart"]')).toBeVisible();
  await tap(page, 'pause.cancelRestart');
  await expect(page.locator('[data-control-id="pause.confirmRestart"]')).toHaveCount(0);
  await tap(page, 'pause.restart');
  await tap(page, 'pause.confirmRestart');
  await waitScreen(page, 'inGame');
  expect(await page.evaluate(() => window.__TC_TEST__?.snapshot().tick ?? 9999)).toBeLessThan(200);
  await expect.poll(async () => page.evaluate(() => window.__TC_TEST__?.isSimPaused() ?? true)).toBe(false);
});

test('[MSN-05] campaign difficulty is chosen, kept and shown; objectives open from pause', async ({ page }, testInfo) => {
  requirePhone(testInfo);
  await gotoQuiet(page);
  await waitForHook(page);
  await page.getByRole('button', { name: 'Campaign', exact: true }).tap();
  await expect(page.locator('[data-control-id="campaignSelect.difficulty.normal"]')).toHaveAttribute('aria-checked', 'true');
  await tap(page, 'campaignSelect.difficulty.hard');
  await expect(page.locator('[data-control-id="campaignSelect.difficulty.hard"]')).toHaveAttribute('aria-checked', 'true');
  await expect(page.locator('.difficulty-note')).toContainText('25% more');
  await page.screenshot({ path: 'test-results/shots/saves-4-difficulty.png' });

  // Kept with the campaign progress across a reload.
  await page.reload();
  await waitForHook(page);
  await page.getByRole('button', { name: 'Campaign', exact: true }).tap();
  await expect(page.locator('[data-control-id="campaignSelect.difficulty.hard"]')).toHaveAttribute('aria-checked', 'true');
  // Training is the same on every difficulty; the story campaigns follow the choice.
  await page.getByRole('button', { name: 'Training', exact: true }).tap();
  await page.locator('[data-mission-id="mission.training.1_drops"]').tap();
  await expect(page.locator('.briefing-difficulty')).toHaveCount(0);
  await tap(page, 'briefing.back');
  await waitScreen(page, 'missionSelect');
  await tap(page, 'missionSelect.back');
  await waitScreen(page, 'campaignSelect');
  await tap(page, 'campaignSelect.human');
  await page.locator('[data-mission-id="mission.human.01_signal_lost"]').tap();
  await expect(page.locator('.briefing-difficulty')).toHaveText('Difficulty: Hard');
  await page.getByRole('button', { name: 'Start mission', exact: true }).tap();
  await waitScreen(page, 'inGame');

  await tap(page, 'inGame.pause');
  await waitScreen(page, 'pause');
  await tap(page, 'pause.objectives');
  await waitScreen(page, 'objectives');
  await tap(page, 'objectives.close');
  await waitScreen(page, 'pause');
  // Still paused under the pause card after looking at the objectives.
  await expect.poll(async () => page.evaluate(() => window.__TC_TEST__?.isSimPaused() ?? false)).toBe(true);
});
