import { expect, test, type Page, type TestInfo } from '@playwright/test';
import { enterGame, waitForHook } from './helpers';

const PHONE_ONLY = 'phone-first WP-10 flow';

function requirePhone(testInfo: TestInfo): void {
  test.skip(testInfo.project.name !== 'phone', PHONE_ONLY);
}

async function tap(page: Page, controlId: string): Promise<void> {
  await page.locator(`[data-control-id="${controlId}"]`).first().tap();
}

async function waitScreen(page: Page, screen: string): Promise<void> {
  await expect.poll(async () => page.evaluate(() => window.__TC_TEST__?.screen() ?? '')).toBe(screen);
}

async function snapshot(page: Page): Promise<{ tick: number; counter: number }> {
  const value = await page.evaluate(() => window.__TC_TEST__?.snapshot() ?? null);
  return { tick: value?.tick ?? 0, counter: value?.counter ?? 0 };
}

test('[GAME-01] pause freezes the sim, refuses orders, and Android back opens and closes the pause menu', async ({ page }, testInfo) => {
  requirePhone(testInfo);
  await enterGame(page);
  await tap(page, 'inGame.pause');
  await waitScreen(page, 'pause');
  await expect.poll(async () => page.evaluate(() => window.__TC_TEST__?.isSimPaused() ?? false)).toBe(true);

  const frozen = await page.evaluate(async () => {
    const hook = window.__TC_TEST__;
    if (!hook) return null;
    const start = hook.snapshot().tick;
    const samples: number[] = [];
    for (let i = 0; i < 6; i += 1) {
      await new Promise<void>((resolve) => {
        window.requestAnimationFrame(() => resolve());
      });
      samples.push(hook.snapshot().tick);
    }
    return { start, samples };
  });
  expect(frozen).not.toBeNull();
  if (!frozen) return;
  expect(frozen.samples.every((tick) => tick === frozen.start)).toBe(true);

  const accepted = await page.evaluate(() => {
    const hook = window.__TC_TEST__;
    if (!hook) return true;
    const id = hook.units().find((unit) => unit.owner === 1)?.id;
    if (id === undefined) return true;
    return hook.sendCommand({
      kind: 'stop',
      unitIds: [id],
      tick: hook.snapshot().tick + 1,
      issuer: 1,
    });
  });
  expect(accepted).toBe(false);

  await tap(page, 'pause.resume');
  await waitScreen(page, 'inGame');
  await expect.poll(async () => (await snapshot(page)).tick).toBeGreaterThan(frozen.start);

  await page.evaluate(() => {
    Object.defineProperty(document, 'hidden', { configurable: true, get: () => true });
    document.dispatchEvent(new Event('visibilitychange'));
  });
  await expect.poll(async () => page.evaluate(() => window.__TC_TEST__?.isSimPaused() ?? false)).toBe(true);
  await page.evaluate(() => {
    Object.defineProperty(document, 'hidden', { configurable: true, get: () => false });
    document.dispatchEvent(new Event('visibilitychange'));
  });
  await expect.poll(async () => page.evaluate(() => window.__TC_TEST__?.isSimPaused() ?? true)).toBe(false);

  await page.evaluate(() => window.__TC_TEST__?.pressAndroidBack());
  await waitScreen(page, 'pause');
  await page.evaluate(() => window.__TC_TEST__?.pressAndroidBack());
  await waitScreen(page, 'inGame');
});

test('[GAME-02] speed settings change the sim multipliers from the top bar and the pause menu', async ({ page }, testInfo) => {
  requirePhone(testInfo);
  await enterGame(page);
  expect(await page.evaluate(() => window.__TC_TEST__?.simSpeed() ?? 0)).toBe(1);
  await tap(page, 'inGame.speed');
  expect(await page.evaluate(() => window.__TC_TEST__?.simSpeed() ?? 0)).toBe(2);
  await tap(page, 'inGame.speed');
  expect(await page.evaluate(() => window.__TC_TEST__?.simSpeed() ?? 0)).toBe(0.5);
  await tap(page, 'inGame.speed');
  expect(await page.evaluate(() => window.__TC_TEST__?.simSpeed() ?? 0)).toBe(1);

  await tap(page, 'inGame.pause');
  await waitScreen(page, 'pause');
  await tap(page, 'pause.speedSlow');
  expect(await page.evaluate(() => window.__TC_TEST__?.simSpeed() ?? 0)).toBe(0.5);
  await tap(page, 'pause.speedNormal');
  expect(await page.evaluate(() => window.__TC_TEST__?.simSpeed() ?? 0)).toBe(1);
});

test('[SAVE-06] manual save and load in a slot restores the identical world hash', async ({ page }, testInfo) => {
  requirePhone(testInfo);
  await enterGame(page);
  await tap(page, 'inGame.pause');
  await waitScreen(page, 'pause');
  // The sim is stopped while the pause overlay is up, so the hash captured here
  // is byte-for-byte the world that gets written to the slot. Capturing it
  // before pausing would record a tick that the save does not contain.
  const savedHash = await page.evaluate(() => window.__TC_TEST__?.worldHash() ?? '');
  await tap(page, 'pause.save');
  await waitScreen(page, 'saveSlots');
  await tap(page, 'saveSlots.save1');
  await expect.poll(async () => page.evaluate(() => window.__TC_TEST__?.lastSaveOutcome()?.status ?? '')).toBe('ok');

  await tap(page, 'saveSlots.back');
  await waitScreen(page, 'pause');
  await tap(page, 'pause.resume');
  await waitScreen(page, 'inGame');
  await expect.poll(async () => page.evaluate(() => window.__TC_TEST__?.worldHash() ?? '')).not.toBe(savedHash);

  await tap(page, 'inGame.pause');
  await waitScreen(page, 'pause');
  await tap(page, 'pause.load');
  await waitScreen(page, 'saveSlots');
  await tap(page, 'saveSlots.load1');
  await expect.poll(async () => page.evaluate(() => window.__TC_TEST__?.lastLoadOutcome()?.status ?? '')).toBe('ok');
  await expect.poll(async () => page.evaluate(() => window.__TC_TEST__?.worldHash() ?? '')).toBe(savedHash);
});

test('[SAVE-08] corrupt and incompatible saves show clear messages and do not crash', async ({ page }, testInfo) => {
  requirePhone(testInfo);
  await enterGame(page);
  await page.evaluate(async () => {
    await window.__TC_TEST__?.writeRawSave('manual-1', '{not a save');
  });
  await tap(page, 'inGame.pause');
  await waitScreen(page, 'pause');
  await tap(page, 'pause.load');
  await waitScreen(page, 'saveSlots');
  await tap(page, 'saveSlots.load1');
  await expect.poll(async () => page.evaluate(() => window.__TC_TEST__?.lastLoadOutcome()?.status ?? '')).toBe('corrupt');
  await expect(page.locator('[data-save-status]')).toContainText('corrupt');

  await page.evaluate(async () => {
    const text = JSON.stringify({ format: 'tcsave', schema: 999, payload: {} });
    await window.__TC_TEST__?.writeRawSave('manual-1', text);
  });
  await tap(page, 'saveSlots.load1');
  await expect.poll(async () => page.evaluate(() => window.__TC_TEST__?.lastLoadOutcome()?.status ?? '')).toBe('incompatible');
  await expect(page.locator('[data-save-status]')).toContainText('incompatible');
});

test('[SAVE-09] resume last game is offered after an autosave and quit offers to save', async ({ page }, testInfo) => {
  requirePhone(testInfo);
  await enterGame(page);

  // Brand the world with a counter value a fresh skirmish cannot reach in a
  // test run, so "resumed the autosave" is distinguishable from "started a new
  // match" without racing the running sim on an exact hash.
  const marker = 50_000;
  await page.evaluate((amount) => {
    const hook = window.__TC_TEST__;
    if (!hook) return;
    const current = hook.snapshot();
    hook.sendCommand({
      kind: 'debug.addCounter',
      amount,
      tick: current.tick + 1,
      issuer: 1,
    });
  }, marker);
  await expect.poll(async () => (await snapshot(page)).counter).toBeGreaterThanOrEqual(marker);

  await page.evaluate(() => window.__TC_TEST__?.requestAutosave());

  await page.reload();
  await waitForHook(page);
  await expect(page.locator('[data-control-id="title.resume"]')).toBeVisible({ timeout: 10_000 });
  await tap(page, 'title.resume');
  await waitScreen(page, 'inGame');
  await expect.poll(async () => (await snapshot(page)).counter).toBeGreaterThanOrEqual(marker);

  await tap(page, 'inGame.pause');
  await waitScreen(page, 'pause');
  await tap(page, 'pause.quit');
  await expect(page.locator('[data-control-id="pause.confirmSaveQuit"]')).toBeVisible();
  await tap(page, 'pause.confirmSaveQuit');
  await waitScreen(page, 'title');
  await expect.poll(async () => page.evaluate(() => window.__TC_TEST__?.lastSaveOutcome()?.status ?? '')).toBe('ok');
});

test('[SAVE-10] web export/import round-trips a save and storage full shows a message', async ({ page }, testInfo) => {
  requirePhone(testInfo);
  await enterGame(page);
  await tap(page, 'inGame.pause');
  await waitScreen(page, 'pause');
  // Paused, so export and import both see the same frozen world.
  const hash = await page.evaluate(() => window.__TC_TEST__?.worldHash() ?? '');
  await tap(page, 'pause.settings');
  await waitScreen(page, 'settings');

  const downloadPromise = page.waitForEvent('download');
  await tap(page, 'settings.export');
  const download = await downloadPromise;
  const path = await download.path();
  expect(path).not.toBeNull();
  if (!path) return;

  await tap(page, 'settings.back');
  await waitScreen(page, 'pause');
  await tap(page, 'pause.resume');
  await waitScreen(page, 'inGame');
  await expect.poll(async () => page.evaluate(() => window.__TC_TEST__?.worldHash() ?? '')).not.toBe(hash);

  await tap(page, 'inGame.pause');
  await waitScreen(page, 'pause');
  await tap(page, 'pause.settings');
  await waitScreen(page, 'settings');
  const chooserPromise = page.waitForEvent('filechooser');
  await tap(page, 'settings.import');
  const chooser = await chooserPromise;
  await chooser.setFiles(path);
  await expect.poll(async () => page.evaluate(() => window.__TC_TEST__?.lastImportOutcome()?.status ?? '')).toBe('ok');
  await expect.poll(async () => page.evaluate(() => window.__TC_TEST__?.worldHash() ?? '')).toBe(hash);

  await page.evaluate(() => window.__TC_TEST__?.setStorageFullForTest(true));
  await tap(page, 'settings.back');
  await waitScreen(page, 'pause');
  await tap(page, 'pause.save');
  await waitScreen(page, 'saveSlots');
  await tap(page, 'saveSlots.save1');
  await expect(page.locator('[data-save-status]')).toContainText('full');
});

test('[SET-01] settings persist across reload and take effect immediately', async ({ page }, testInfo) => {
  requirePhone(testInfo);
  await enterGame(page);
  await tap(page, 'inGame.pause');
  await waitScreen(page, 'pause');
  await tap(page, 'pause.settings');
  await waitScreen(page, 'settings');

  await tap(page, 'settings.graphicsQuality');
  await tap(page, 'settings.textSize');
  await tap(page, 'settings.haptics');
  await tap(page, 'settings.edgeScroll');
  await expect.poll(async () => page.evaluate(() => window.__TC_TEST__?.settings().graphicsQuality ?? '')).not.toBe('auto');
  await expect.poll(async () => page.evaluate(() => document.documentElement.dataset.textSize ?? '')).toBe('large');
  await expect.poll(async () => page.evaluate(() => window.__TC_TEST__?.quality().level ?? 0)).toBeGreaterThan(0);

  // Drive the volume slider by firing the exact `input` event that the native
  // range control fires when its thumb moves. Synthetic pointer presses on a
  // mobile-emulated viewport route through the row's label wrapper and do not
  // reposition the thumb, so the earlier physical press left the value at the
  // default and made the persistence check race. The event we dispatch is what
  // SET-01 actually cares about (settings take effect immediately), and the
  // reload below proves the resulting value persists.
  await page.locator('[data-setting="masterVolume"]').evaluate((element) => {
    if (!(element instanceof HTMLInputElement)) {
      return;
    }
    element.value = '0.25';
    element.dispatchEvent(new Event('input', { bubbles: true }));
  });
  await expect.poll(async () => page.evaluate(() => window.__TC_TEST__?.settings().masterVolume ?? 1)).toBeLessThan(0.8);

  await page.reload();
  await waitForHook(page);
  await expect.poll(async () => page.evaluate(() => window.__TC_TEST__?.settings().textSize ?? '')).toBe('large');
  await expect.poll(async () => page.evaluate(() => window.__TC_TEST__?.settings().haptics ?? true)).toBe(false);
  await expect.poll(async () => page.evaluate(() => window.__TC_TEST__?.settings().masterVolume ?? 1)).toBeLessThan(0.8);
});

test('[AUD-02] no audio starts before the first user gesture', async ({ page }, testInfo) => {
  requirePhone(testInfo);
  await page.goto('/');
  await waitForHook(page);
  expect(await page.evaluate(() => window.__TC_TEST__?.audioStatus().unlocked ?? true)).toBe(false);
  await page.getByRole('button', { name: 'Skirmish', exact: true }).tap();
  await expect.poll(async () => page.evaluate(() => window.__TC_TEST__?.audioStatus().unlocked ?? false)).toBe(true);
});

test('[AUD-01] selection and orders play audio acknowledgements', async ({ page }, testInfo) => {
  requirePhone(testInfo);
  await enterGame(page);
  const unit = await page.evaluate(() => {
    const hook = window.__TC_TEST__;
    if (!hook) return null;
    const own = hook.units().find((item) => item.owner === 1);
    if (!own) return null;
    const screen = hook.unitScreenCentre(own.id);
    return screen ? { id: own.id, screen } : null;
  });
  expect(unit).not.toBeNull();
  if (!unit) return;
  await page.touchscreen.tap(unit.screen.x, unit.screen.y);
  await expect.poll(async () => page.evaluate(() => window.__TC_TEST__?.audioStatus().played ?? [])).toContain('selection');
  const ground = await page.evaluate(() => {
    const hook = window.__TC_TEST__;
    if (!hook) return null;
    // Since WP-04 the start area holds a pad, workers and deposits, so pick a
    // ground point on screen that is clear of all of them (a tap there is an order, not a selection).
    const cam = hook.camera();
    const things = [
      ...hook.units().map((item) => ({ x: item.x, z: item.z })),
      ...hook.structures().map((item) => ({ x: item.x, z: item.z })),
      ...hook.deposits().map((item) => ({ x: item.x, z: item.z })),
    ];
    const offsets: Array<[number, number]> = [];
    for (const radius of [8, 12, 16]) {
      for (let step = 0; step < 12; step += 1) {
        const angle = (step / 12) * Math.PI * 2;
        offsets.push([Math.cos(angle) * radius, Math.sin(angle) * radius]);
      }
    }
    for (const [dx, dz] of offsets) {
      const x = cam.targetX + dx;
      const z = cam.targetZ + dz;
      if (things.every((item) => Math.hypot(item.x - x, item.z - z) > 6)) {
        const point = hook.worldToScreen(x, z);
        // Skip points covered by the HUD (group tiles, command grid, panels).
        const hit = document.elementFromPoint(point.x, point.y);
        if (hit instanceof HTMLCanvasElement && hit.classList.contains('game-canvas')) {
          return point;
        }
      }
    }
    return null;
  });
  expect(ground).not.toBeNull();
  if (!ground) return;
  await page.touchscreen.tap(ground.x, ground.y);
  await expect.poll(async () => page.evaluate(() => window.__TC_TEST__?.audioStatus().played ?? [])).toContain('orderAck');
});

test('[ALRT-01] alerts are rate-limited and tapping a toast jumps the camera', async ({ page }, testInfo) => {
  requirePhone(testInfo);
  await enterGame(page);
  await page.evaluate(() => {
    window.__TC_TEST__?.raiseAlert('depositEmpty', 30, -30);
    window.__TC_TEST__?.raiseAlert('depositEmpty', 30, -30);
  });
  await expect(page.locator('.alert-toast')).toHaveCount(1);
  // A plain touch at the toast. Locator.tap() re-checks the element between slow frames
  // (software rendering of the full models), and the toast can time out meanwhile.
  const box = await page.locator('.alert-toast').boundingBox();
  expect(box).not.toBeNull();
  if (!box) return;
  await page.touchscreen.tap(box.x + box.width / 2, box.y + box.height / 2);
  await expect.poll(async () => {
    const camera = await page.evaluate(() => window.__TC_TEST__?.camera() ?? null);
    if (!camera) return 999;
    return Math.hypot(camera.targetX - 30, camera.targetZ + 30);
  }).toBeLessThan(1);
});

test('[BUG-01] bug report collects fields and saves a report without a network request', async ({ page }, testInfo) => {
  requirePhone(testInfo);
  await enterGame(page);
  await tap(page, 'inGame.pause');
  await waitScreen(page, 'pause');
  await tap(page, 'pause.bugReport');
  await waitScreen(page, 'bugReport');
  await page.locator('.bug-text').fill('Tank drove through a hill.');
  await page.locator('[data-setting="bugReport.includeSave"]').check();
  await page.evaluate(() => {
    const target = window as unknown as { __fetchCount: number };
    target.__fetchCount = 0;
    const original = window.fetch;
    window.fetch = (...args) => {
      target.__fetchCount += 1;
      return original(...args);
    };
  });
  await tap(page, 'bugReport.save');
  await expect(page.locator('[data-bug-status]')).toContainText('Saved');
  const report = await page.evaluate(() => window.__TC_TEST__?.lastBugReport() ?? null);
  expect(report).not.toBeNull();
  if (!report) return;
  expect(report.content).toContain('Tank drove through a hill.');
  expect(report.content).toContain('device');
  expect(report.content).toContain('logs');
  expect(report.content).toContain('lastFreezeReport');
  const fetchCount = await page.evaluate(() => (window as unknown as { __fetchCount: number }).__fetchCount);
  expect(fetchCount).toBe(0);
});
