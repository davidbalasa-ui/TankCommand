import { mkdirSync } from 'node:fs';
import { join } from 'node:path';
import { expect, test, type Page } from '@playwright/test';
import { enterGame, openBuildMenu, toggleLeftHandedViaSettings, winSkirmish } from './helpers';

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
  await toggleLeftHandedViaSettings(page);
  await expect
    .poll(async () => page.evaluate(() => window.__TC_TEST__?.hud()?.leftHanded ?? false))
    .toBe(true);
  await waitFrames(page, 3);
  await page.screenshot({ path: 'test-results/shots/wp03-5-left-handed.png' });
});

test('[screens] wp10-1-pause-menu', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'phone', PHONE_ONLY);
  await enterGame(page);
  await page.locator('[data-control-id="inGame.pause"]').tap();
  await expect.poll(async () => page.evaluate(() => window.__TC_TEST__?.screen() ?? '')).toBe('pause');
  await page.screenshot({ path: 'test-results/shots/wp10-1-pause-menu.png' });
});

test('[screens] wp10-2-settings', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'phone', PHONE_ONLY);
  await enterGame(page);
  await page.locator('[data-control-id="inGame.pause"]').tap();
  await expect.poll(async () => page.evaluate(() => window.__TC_TEST__?.screen() ?? '')).toBe('pause');
  await page.locator('[data-control-id="pause.settings"]').tap();
  await expect.poll(async () => page.evaluate(() => window.__TC_TEST__?.screen() ?? '')).toBe('settings');
  await page.screenshot({ path: 'test-results/shots/wp10-2-settings.png' });
});

test('[screens] wp10-3-save-slots', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'phone', PHONE_ONLY);
  await enterGame(page);
  await page.locator('[data-control-id="inGame.pause"]').tap();
  await expect.poll(async () => page.evaluate(() => window.__TC_TEST__?.screen() ?? '')).toBe('pause');
  await page.locator('[data-control-id="pause.save"]').tap();
  await expect.poll(async () => page.evaluate(() => window.__TC_TEST__?.screen() ?? '')).toBe('saveSlots');
  await page.screenshot({ path: 'test-results/shots/wp10-3-save-slots.png' });
});

test('[screens] wp10-4-alert-toast', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'phone', PHONE_ONLY);
  await enterGame(page);
  await page.evaluate(() => window.__TC_TEST__?.raiseAlert('padLost', 25, -25));
  await expect(page.locator('.alert-toast')).toBeVisible();
  await page.screenshot({ path: 'test-results/shots/wp10-4-alert-toast.png' });
});

test('[screens] wp10-5-bug-report', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'phone', PHONE_ONLY);
  await enterGame(page);
  await page.locator('[data-control-id="inGame.pause"]').tap();
  await expect.poll(async () => page.evaluate(() => window.__TC_TEST__?.screen() ?? '')).toBe('pause');
  await page.locator('[data-control-id="pause.bugReport"]').tap();
  await expect.poll(async () => page.evaluate(() => window.__TC_TEST__?.screen() ?? '')).toBe('bugReport');
  await page.locator('.bug-text').fill('Sample report for the visual review.');
  await page.screenshot({ path: 'test-results/shots/wp10-5-bug-report.png' });
});

test('[screens] wp04-1-start-of-match', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'phone', PHONE_ONLY);
  await enterGame(page);
  await waitFrames(page, 3);
  await page.screenshot({ path: 'test-results/shots/wp04-1-start-of-match.png' });
});

test('[screens] wp04-2-build-menu-open', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'phone', PHONE_ONLY);
  await enterGame(page);
  await openBuildMenu(page);
  await expect
    .poll(async () => page.evaluate(() => window.__TC_TEST__?.hud()?.buildMenuOpen ?? false))
    .toBe(true);
  await waitFrames(page, 3);
  await page.screenshot({ path: 'test-results/shots/wp04-2-build-menu-open.png' });
});

test('[screens] wp04-3-queue-in-progress', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'phone', PHONE_ONLY);
  await enterGame(page);
  await openBuildMenu(page);
  // The build menu is opened with the units section already populated; tapping
  // the scout orders one through the normal drop path, so the queue bar shows
  // whatever progress the sim has reached for this item.
  await page.locator('[data-control-id="build.item.unit.human.scout"]').tap();
  await expect
    .poll(async () => page.evaluate(() => window.__TC_TEST__?.hud()?.queue.length ?? 0))
    .toBe(1);
  await expect
    .poll(async () => page.evaluate(() => window.__TC_TEST__?.hud()?.queue[0]?.progress ?? 0))
    .toBeGreaterThan(0);
  await waitFrames(page, 3);
  await page.screenshot({ path: 'test-results/shots/wp04-3-queue-in-progress.png' });
});

test('[screens] wp04-4-placing-structure-kit', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'phone', PHONE_ONLY);
  await enterGame(page);
  await page.evaluate(() => window.__TC_TEST__?.setSimSpeed(8));
  const padId = await page.evaluate(() => {
    const hook = window.__TC_TEST__;
    return hook?.structures().find((s) => s.owner === 1 && s.kind === 'pad')?.id ?? null;
  });
  expect(padId).not.toBeNull();
  if (padId === null) {
    return;
  }
  await page.evaluate((id) => {
    const hook = window.__TC_TEST__;
    if (hook) {
      hook.sendCommand({
        kind: 'buy',
        itemId: 'structure.human.landing_pad',
        padId: id,
        tick: hook.snapshot().tick + 1,
        issuer: 1,
      });
    }
  }, padId);
  await expect
    .poll(async () => page.evaluate(() => window.__TC_TEST__?.dropState().kits.length ?? 0), {
      timeout: 20_000,
    })
    .toBe(1);
  const kitId = await page.evaluate(() => window.__TC_TEST__?.dropState().kits[0]?.id ?? null);
  expect(kitId).not.toBeNull();
  if (kitId === null) {
    return;
  }
  await page.locator('[data-control-id="inGame.buildMenu"]').tap();
  await page.locator(`[data-control-id="build.place.${kitId}"]`).tap();
  await expect
    .poll(async () => page.evaluate(() => window.__TC_TEST__?.placement() !== null))
    .toBe(true);
  await page.evaluate(() => window.__TC_TEST__?.setCamera({ targetX: -35, targetZ: -46, distance: 60, yaw: 0 }));
  const screen = await page.evaluate(() => window.__TC_TEST__?.worldToScreen(-35, -46) ?? null);
  expect(screen).not.toBeNull();
  if (!screen) {
    return;
  }
  await page.evaluate((point) => {
    const canvas = document.querySelector('canvas.game-canvas');
    if (!canvas) return;
    const fire = (type: string, x: number, y: number, buttons: number): void => {
      canvas.dispatchEvent(
        new PointerEvent(type, {
          bubbles: true,
          cancelable: true,
          pointerId: 1,
          pointerType: 'touch',
          clientX: x,
          clientY: y,
          button: 0,
          buttons,
        }),
      );
    };
    fire('pointerdown', point.x, point.y, 1);
    fire('pointermove', point.x + 8, point.y + 8, 1);
    fire('pointerup', point.x + 8, point.y + 8, 0);
  }, screen);
  await expect
    .poll(async () => page.evaluate(() => window.__TC_TEST__?.placement()?.valid ?? false))
    .toBe(true);
  await waitFrames(page, 3);
  await page.screenshot({ path: 'test-results/shots/wp04-4-placing-structure-kit.png' });
});

test('[screens] wp04-5-miners-working', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'phone', PHONE_ONLY);
  await enterGame(page);
  await page.evaluate(() => window.__TC_TEST__?.setSimSpeed(8));
  const miner = await page.evaluate(() => {
    const hook = window.__TC_TEST__;
    if (!hook) return null;
    return hook.units().find((u) => u.owner === 1 && u.workerKind === 'oreMiner') ?? null;
  });
  const deposit = await page.evaluate(() => window.__TC_TEST__?.deposits().find((d) => d.kind === 'ore') ?? null);
  expect(miner).not.toBeNull();
  expect(deposit).not.toBeNull();
  if (!miner || !deposit) {
    return;
  }
  await page.evaluate(({ unitId, depositId }) => {
    const hook = window.__TC_TEST__;
    if (!hook) return;
    hook.setCamera({ targetX: hook.units().find((u) => u.id === unitId)?.x ?? 0, targetZ: hook.units().find((u) => u.id === unitId)?.z ?? 0, distance: 40, yaw: 0 });
    hook.setSelection([unitId]);
    hook.sendCommand({
      kind: 'mine',
      unitIds: [unitId],
      depositId,
      tick: hook.snapshot().tick + 1,
      issuer: 1,
    });
  }, { unitId: miner.id, depositId: deposit.id });
  await expect
    .poll(async () => page.evaluate((id) => window.__TC_TEST__?.units().find((u) => u.id === id)?.jobKind ?? null, miner.id))
    .toBe('oreMiner');
  await waitFrames(page, 3);
  await page.screenshot({ path: 'test-results/shots/wp04-5-miners-working.png' });
});

test('[screens] wp04-6-victory-results', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'phone', PHONE_ONLY);
  test.setTimeout(180_000);
  await enterGame(page);
  await winSkirmish(page);
  // `winSkirmish` leaves the game on the results screen, which unmounts the
  // inGame HUD and disposes the renderer. `renderStats().frame` therefore
  // returns 0 forever: waiting on frames after victory can never advance.
  await expect(page.locator('[data-screen-id="results"] h1')).toBeVisible();
  await page.screenshot({ path: 'test-results/shots/wp04-6-victory-results.png' });
});
