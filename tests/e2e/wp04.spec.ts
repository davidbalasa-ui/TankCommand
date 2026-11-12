import { expect, test, type Page, type TestInfo } from '@playwright/test';
import { enterGame, openBuildMenu, winSkirmish } from './helpers';

const PHONE_ONLY = 'phone-only touch flow';

async function tapUnit(page: Page, id: number): Promise<void> {
  await page.evaluate((unitId) => {
    const hook = window.__TC_TEST__;
    const unit = hook?.units().find((item) => item.id === unitId);
    if (hook && unit) {
      hook.setCamera({ targetX: unit.x, targetZ: unit.z, distance: 40, yaw: 0 });
    }
  }, id);
  // Read the unit's screen point only after two animation frames with the new camera (the sim
  // may be paused, so count browser frames rather than rendered game frames).
  await page.evaluate(
    () => new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))),
  );
  const point = await page.evaluate((unitId) => window.__TC_TEST__?.unitScreenCentre(unitId) ?? null, id);
  expect(point).not.toBeNull();
  if (!point) {
    return;
  }
  await page.touchscreen.tap(point.x, point.y);
}

async function tapWorldPoint(page: Page, x: number, z: number): Promise<void> {
  const point = await page.evaluate(({ wx, wz }) => {
    const hook = window.__TC_TEST__;
    if (!hook) {
      return null;
    }
    hook.setCamera({ targetX: wx, targetZ: wz, distance: 40, yaw: 0 });
    return hook.worldToScreen(wx, wz);
  }, { wx: x, wz: z });
  expect(point).not.toBeNull();
  if (!point) {
    return;
  }
  await page.touchscreen.tap(point.x, point.y);
}

test('[HUD-05] build menu, live resources, queue and cancel work by touch', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'phone', PHONE_ONLY);
  // The open Build drawer over the detailed models renders slowly in software.
  test.setTimeout(60_000);
  await enterGame(page);
  await expect
    .poll(async () => page.evaluate(() => window.__TC_TEST__?.hud()?.ore ?? -1))
    .toBe(600);

  await openBuildMenu(page);
  await expect
    .poll(async () => page.evaluate(() => window.__TC_TEST__?.hud()?.buildMenuOpen ?? false))
    .toBe(true);
  await expect
    .poll(async () => page.evaluate(() => window.__TC_TEST__?.hud()?.selectedPadId ?? null))
    .not.toBeNull();

  await page.locator('[data-control-id="build.item.unit.human.scout"]').tap();
  await expect
    .poll(async () => page.evaluate(() => window.__TC_TEST__?.hud()?.ore ?? 0))
    .toBe(550);
  await expect
    .poll(async () => page.evaluate(() => window.__TC_TEST__?.hud()?.queue.length ?? 0))
    .toBe(1);
  // A second order waits behind the first, so it is still cancellable however slowly the browser
  // renders (the first can land before a slow tap arrives).
  await page.locator('[data-control-id="build.item.unit.human.scout"]').tap();
  await expect
    .poll(async () => page.evaluate(() => window.__TC_TEST__?.hud()?.ore ?? 0))
    .toBe(500);
  const orderId = await page.evaluate(() => window.__TC_TEST__?.hud()?.queue.at(-1)?.id ?? null);
  expect(orderId).not.toBeNull();
  if (orderId === null) {
    return;
  }
  await page.locator(`[data-control-id="build.cancel.${orderId}"]`).tap();
  await expect
    .poll(async () => page.evaluate(() => window.__TC_TEST__?.hud()?.ore ?? 0))
    .toBe(550);
  await expect
    .poll(async () =>
      page.evaluate((id) => window.__TC_TEST__?.hud()?.queue.some((order) => order.id === id) ?? true, orderId),
    )
    .toBe(false);
});

test('[HUD-05] miner deposit tap, mine command and salvage button work by touch', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'phone', PHONE_ONLY);
  // Full models from the first frame make software rendering slow; this ran at ~29 of 30 s.
  test.setTimeout(60_000);
  await enterGame(page);
  const miner = await page.evaluate(() => {
    const hook = window.__TC_TEST__;
    return hook?.units().find((unit) => unit.owner === 1 && unit.workerKind === 'oreMiner') ?? null;
  });
  const deposit = await page.evaluate(() => {
    const hook = window.__TC_TEST__;
    return hook?.deposits().find((item) => item.kind === 'ore') ?? null;
  });
  expect(miner).not.toBeNull();
  expect(deposit).not.toBeNull();
  if (!miner || !deposit) {
    return;
  }
  await tapUnit(page, miner.id);
  await expect
    .poll(async () => page.evaluate(() => window.__TC_TEST__?.selection() ?? []))
    .toContain(miner.id);
  await expect
    .poll(async () =>
      page.evaluate(
        () => document.querySelector<HTMLButtonElement>('[data-control-id="inGame.mine"]')?.disabled ?? true,
      ),
    )
    .toBe(false);
  await page.locator('[data-control-id="inGame.mine"]').tap();
  await tapWorldPoint(page, deposit.x, deposit.z);
  await expect
    .poll(async () =>
      page.evaluate((id) => window.__TC_TEST__?.units().find((unit) => unit.id === id)?.jobKind ?? null, miner.id),
    )
    .toBe('oreMiner');

  const tug = await page.evaluate(() => {
    const hook = window.__TC_TEST__;
    return hook?.units().find((unit) => unit.owner === 1 && unit.workerKind === 'tug') ?? null;
  });
  expect(tug).not.toBeNull();
  if (!tug) {
    return;
  }
  const oreBefore = await page.evaluate(() => window.__TC_TEST__?.hud()?.ore ?? 0);
  // The tug drives between the pad and the miner, and software rendering is slow, so a tap can
  // land just behind it: tap again (at its new position) until it is selected.
  await expect(async () => {
    await tapUnit(page, tug.id);
    expect(await page.evaluate((id) => window.__TC_TEST__?.selection().includes(id) ?? false, tug.id)).toBe(true);
  }).toPass({ timeout: 20_000 });
  // The salvage button is enabled for *any* selected worker, so a tap that
  // missed the tug would leave the earlier miner selected and still satisfy the
  // enabled check. Verify the tug actually became the selection before
  // salvaging.
  await expect
    .poll(async () =>
      page.evaluate((id) => window.__TC_TEST__?.selection().includes(id) ?? false, tug.id),
    )
    .toBe(true);
  await expect
    .poll(async () =>
      page.evaluate(
        () => document.querySelector<HTMLButtonElement>('[data-control-id="inGame.salvage"]')?.disabled ?? true,
      ),
    )
    .toBe(false);
  await page.locator('[data-control-id="inGame.salvage"]').tap();
  // Both sides start with a tug, so `some(workerKind === 'tug')` is never false
  // even after the player's tug has been salvaged. The requirement is about
  // *own* workers, so filter by owner.
  await expect
    .poll(async () =>
      page.evaluate(
        () =>
          window.__TC_TEST__?.units().some(
            (unit) => unit.owner === 1 && unit.workerKind === 'tug',
          ) ?? false,
      ),
    )
    .toBe(false);
  await expect
    .poll(async () => page.evaluate(() => window.__TC_TEST__?.hud()?.ore ?? 0))
    .toBe(oreBefore + 35);
});

test('[HUD-05] tug assign button works by touch after a station is placed', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'phone', PHONE_ONLY);
  await enterGame(page);
  await page.evaluate(() => window.__TC_TEST__?.setSimSpeed(8));
  const padId = await page.evaluate(() => {
    const hook = window.__TC_TEST__;
    return hook?.structures().find((item) => item.owner === 1 && item.kind === 'pad')?.id ?? null;
  });
  // Pick a metal deposit that clears every unit: the start miner sits 2.83
  // units from the first metal deposit and `placementValidity` correctly
  // refuses the kit with `'overlap'`. The second metal deposit has no unit
  // within 4.5 units, so the placement succeeds.
  const deposit = await page.evaluate(() => {
    const hook = window.__TC_TEST__;
    if (!hook) {
      return null;
    }
    const units = hook.units();
    for (const item of hook.deposits()) {
      if (item.kind !== 'metal') {
        continue;
      }
      const clearOfUnits = units.every(
        (unit) => Math.hypot(unit.x - item.x, unit.z - item.z) >= 4.5,
      );
      if (clearOfUnits) {
        return { id: item.id, x: item.x, z: item.z };
      }
    }
    return null;
  });
  expect(padId).not.toBeNull();
  expect(deposit).not.toBeNull();
  if (padId === null || !deposit) {
    return;
  }
  await page.evaluate((id) => {
    const hook = window.__TC_TEST__;
    if (hook) {
      hook.sendCommand({
        kind: 'buy',
        itemId: 'structure.human.metal_station',
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
  await page.evaluate(({ id, x, z }) => {
    const hook = window.__TC_TEST__;
    if (hook) {
      hook.sendCommand({
        kind: 'placeKit',
        kitId: id,
        x,
        z,
        tick: hook.snapshot().tick + 1,
        issuer: 1,
      });
    }
  }, { id: kitId, x: deposit.x, z: deposit.z });
  await expect
    .poll(async () => page.evaluate(() => window.__TC_TEST__?.structures().some((s) => s.owner === 1 && s.kind === 'metalStation') ?? false), {
      timeout: 10_000,
    })
    .toBe(true);
  const station = await page.evaluate(() => {
    const hook = window.__TC_TEST__;
    return hook?.structures().find((s) => s.owner === 1 && s.kind === 'metalStation') ?? null;
  });
  const tug = await page.evaluate(() => {
    const hook = window.__TC_TEST__;
    return hook?.units().find((unit) => unit.owner === 1 && unit.workerKind === 'tug') ?? null;
  });
  expect(station).not.toBeNull();
  expect(tug).not.toBeNull();
  if (!station || !tug) {
    return;
  }
  // Haulers drive off to work by themselves: hold the sim still while tapping so the tap lands on
  // this one (on a slow software-rendered browser it could drive past another worker first).
  await page.evaluate(() => {
    window.__TC_TEST__?.setSimSpeed(1);
    window.__TC_TEST__?.pauseSim(true);
  });
  await tapUnit(page, tug.id);
  await expect
    .poll(async () =>
      page.evaluate(
        () => document.querySelector<HTMLButtonElement>('[data-control-id="inGame.assign"]')?.disabled ?? true,
      ),
    )
    .toBe(false);
  await page.locator('[data-control-id="inGame.assign"]').tap();
  await tapWorldPoint(page, station.x, station.z);
  await page.evaluate(() => window.__TC_TEST__?.pauseSim(false));
  await expect
    .poll(async () =>
      page.evaluate((id) => {
        const unit = window.__TC_TEST__?.units().find((item) => item.id === id);
        return unit ? `${unit.jobSource}:${unit.jobTargetId}` : null;
      }, tug.id),
    )
    .toBe(`station:${station.id}`);
});

test('[DROP-04] structure kit ghost, cancel and confirm work by touch', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'phone', PHONE_ONLY);
  // Drop, two placements and the build-out run close to the default 30 s under
  // software rendering (it timed out at the last step before the HUD change too).
  // Matches now start only once the full models are in, which slows each frame further.
  test.setTimeout(120_000);
  await enterGame(page);
  await page.evaluate(() => window.__TC_TEST__?.setSimSpeed(8));
  const padId = await page.evaluate(() => {
    const hook = window.__TC_TEST__;
    return hook?.structures().find((item) => item.owner === 1 && item.kind === 'pad')?.id ?? null;
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

  // The Place tile sits in the queue strip at the top of the screen.
  await page.locator(`[data-control-id="build.place.${kitId}"]`).tap();
  await expect
    .poll(async () => page.evaluate(() => window.__TC_TEST__?.placement() !== null))
    .toBe(true);
  await page.evaluate(() => window.__TC_TEST__?.setCamera({ targetX: -24, targetZ: -64, distance: 60, yaw: 0 }));
  const screen = await page.evaluate(() => window.__TC_TEST__?.worldToScreen(-24, -64) ?? null);
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
  await page.locator('[data-control-id="inGame.placeCancel"]').tap();
  await expect
    .poll(async () => page.evaluate(() => window.__TC_TEST__?.placement() === null))
    .toBe(true);
  await expect
    .poll(async () => page.evaluate(() => window.__TC_TEST__?.dropState().kits.length ?? 0))
    .toBe(1);

  // The Place tile sits in the queue strip at the top of the screen.
  await page.locator(`[data-control-id="build.place.${kitId}"]`).tap();
  await page.evaluate(() => window.__TC_TEST__?.setCamera({ targetX: -24, targetZ: -64, distance: 60, yaw: 0 }));
  const again = await page.evaluate(() => window.__TC_TEST__?.worldToScreen(-24, -64) ?? null);
  expect(again).not.toBeNull();
  if (!again) {
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
    fire('pointerup', point.x, point.y, 0);
  }, again);
  await expect
    .poll(async () => page.evaluate(() => window.__TC_TEST__?.placement()?.valid ?? false))
    .toBe(true);
  await page.locator('[data-control-id="inGame.placeConfirm"]').tap();
  await expect
    .poll(async () =>
      page.evaluate(
        () => window.__TC_TEST__?.structures().filter((s) => s.owner === 1 && s.kind === 'pad').length ?? 0,
      ),
    )
    .toBe(2);
});

test('[MATCH-02] results screen shows outcome, time and match totals', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'phone', PHONE_ONLY);
  test.setTimeout(180_000);
  await enterGame(page);
  await winSkirmish(page);
  const heading = await page.locator('[data-screen-id="results"] h1').textContent();
  expect(heading).toBe('Victory');
  const detail = await page.locator('[data-screen-id="results"] .results-stats').textContent();
  expect(detail).toContain('Time');
  expect(detail).toContain('Units built');
  expect(detail).toContain('Units lost');
  expect(detail).toContain('Ore gathered');
  expect(detail).toContain('Metal gathered');
});
