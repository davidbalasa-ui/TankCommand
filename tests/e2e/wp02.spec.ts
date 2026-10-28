import { expect, test, type Page, type TestInfo } from '@playwright/test';
import {
  countDistinctPngColors,
  enterGame,
  type TestCamera,
  type TestUnit,
} from './helpers';

function isTouch(testInfo: TestInfo): boolean {
  return testInfo.project.name !== 'desktop';
}

async function units(page: Page): Promise<TestUnit[]> {
  return page.evaluate(() => window.__TC_TEST__?.units() ?? []);
}

async function selectUnit(page: Page, x: number, y: number, touch: boolean): Promise<void> {
  if (touch) {
    await page.touchscreen.tap(x, y);
  } else {
    await page.mouse.click(x, y);
  }
}

async function orderAt(page: Page, x: number, y: number, touch: boolean): Promise<void> {
  if (touch) {
    await page.touchscreen.tap(x, y);
  } else {
    await page.mouse.click(x, y, { button: 'right' });
  }
}

async function setCamera(page: Page, info: Partial<TestCamera>): Promise<void> {
  await page.evaluate((camera) => {
    window.__TC_TEST__?.setCamera(camera);
  }, info);
  await page.waitForTimeout(80);
}

async function camera(page: Page): Promise<TestCamera> {
  return page.evaluate(() => window.__TC_TEST__?.camera() ?? {
    targetX: 0,
    targetZ: 0,
    distance: 60,
    yaw: 0,
    pitch: 0,
  });
}

/**
 * Waits until at least one fixed step has run since the order was issued and then
 * freezes the sim, so the order can be read without racing the unit's arrival.
 */
async function freezeAfterNextStep(page: Page): Promise<void> {
  await page.evaluate(async () => {
    const hook = window.__TC_TEST__;
    if (!hook) {
      return;
    }
    const start = hook.snapshot().tick;
    for (let i = 0; i < 900 && hook.snapshot().tick === start; i += 1) {
      await new Promise((resolve) => setTimeout(resolve, 10));
    }
    hook.pauseSim(true);
  });
}

async function dispatchPointer(
  page: Page,
  type: string,
  id: number,
  x: number,
  y: number,
): Promise<void> {
  await page.evaluate(
    ({ eventType, pointerId, clientX, clientY }) => {
      const canvas = document.querySelector('canvas');
      if (!canvas) {
        return;
      }
      canvas.dispatchEvent(
        new PointerEvent(eventType, {
          bubbles: true,
          cancelable: true,
          pointerId,
          pointerType: 'touch',
          clientX,
          clientY,
          button: 0,
          buttons: eventType === 'pointerup' ? 0 : 1,
        }),
      );
    },
    { eventType: type, pointerId: id, clientX: x, clientY: y },
  );
}

interface SamplePoint {
  x: number;
  z: number;
  reachable: boolean;
}

/**
 * Two points sit within 10 world units of opposite map corners — the case where
 * ground picking is most likely to break (extreme zoom-out, camera far outside
 * the terrain bounds) — and three sit in the flattened start area at a known
 * distance from every tank, where the sim is guaranteed to accept the
 * destination exactly, so the resulting move order can be asserted too.
 */
const SAMPLE_POINTS: readonly SamplePoint[] = [
  { x: -68, z: -58, reachable: true },
  { x: -58, z: -68, reachable: true },
  { x: -64, z: -64, reachable: true },
  { x: 74, z: 74, reachable: false }, // 8.5 units from the (80, 80) corner
  { x: -74, z: 74, reachable: false }, // 8.5 units from the (-80, 80) corner
];

const CAMERA_SETTINGS = [
  { distance: 20, yaw: 0 },
  { distance: 60, yaw: 1 },
  { distance: 120, yaw: 2 },
];

test('[INP-01] ground picks and ground orders land at the picked point across camera settings', async ({
  page,
}, testInfo) => {
  test.setTimeout(180_000);
  await enterGame(page);
  const touch = isTouch(testInfo);
  const own = (await units(page)).filter((unit) => unit.owner === 1);
  const unit = own[0];
  expect(unit).toBeDefined();
  if (!unit) {
    return;
  }

  const deselect = page.getByRole('button', { name: 'Deselect', exact: true });
  const stop = page.getByRole('button', { name: 'Stop', exact: true });

  for (const setting of CAMERA_SETTINGS) {
    for (const point of SAMPLE_POINTS) {
      const label = `(${point.x}, ${point.z}) at distance ${setting.distance}`;

      // Every sample starts from a known selection state: an order tap can only
      // be a move when something is selected, and a corner tap with no selection
      // would deselect rather than pick.
      if (touch) {
        await deselect.tap();
      } else {
        await deselect.click();
      }
      await expect
        .poll(async () => page.evaluate(() => window.__TC_TEST__?.selection() ?? []))
        .toEqual([]);

      if (point.reachable) {
        const current = (await units(page)).find((item) => item.id === unit.id);
        expect(current, label).toBeDefined();
        if (!current) {
          return;
        }
        // Centre the camera on the tank at a comfortable zoom, then click at the
        // unit's picking centre (the same projection `pickUnit` compares against
        // its radius). Clicking at the ground base — what `worldToScreen` returns
        // — is not the same thing: the pick centre sits UNIT_PICK_HEIGHT above
        // the base, and at distance 20 that offset is over the 24 px pick radius
        // on wide viewports.
        await setCamera(page, {
          targetX: current.x,
          targetZ: current.z,
          distance: 60,
          yaw: 0,
        });
        const unitScreen = await page.evaluate(
          (id) => window.__TC_TEST__?.unitScreenCentre(id) ?? null,
          unit.id,
        );
        expect(unitScreen, label).not.toBeNull();
        if (!unitScreen) {
          return;
        }
        await selectUnit(page, unitScreen.x, unitScreen.y, touch);
        await expect
          .poll(async () => page.evaluate(() => window.__TC_TEST__?.selection() ?? []))
          .toContain(unit.id);
      }

      await setCamera(page, {
        targetX: point.x,
        targetZ: point.z,
        distance: setting.distance,
        yaw: setting.yaw,
      });

      const screen = await page.evaluate(
        ({ x, z }) => window.__TC_TEST__?.worldToScreen(x, z) ?? { x: 0, y: 0 },
        point,
      );
      await orderAt(page, screen.x, screen.y, touch);
      await freezeAfterNextStep(page);

      // Raw picking: must land on the requested ground point at every zoom, for
      // every sample, reachable or not.
      const picked = await page.evaluate(() => window.__TC_TEST__?.lastGroundPick() ?? null);
      expect(picked, label).not.toBeNull();
      expect(
        Math.hypot((picked?.x ?? 0) - point.x, (picked?.z ?? 0) - point.z),
        `${label}: ground pick (${picked?.x ?? 0}, ${picked?.z ?? 0})`,
      ).toBeLessThanOrEqual(1);

      if (point.reachable) {
        const ordered = (await units(page)).find((item) => item.id === unit.id);
        expect(ordered?.orderX, label).not.toBeNull();
        expect(ordered?.orderZ, label).not.toBeNull();
        expect(
          Math.hypot((ordered?.orderX ?? 0) - point.x, (ordered?.orderZ ?? 0) - point.z),
          `${label}: order (${ordered?.orderX ?? 0}, ${ordered?.orderZ ?? 0})`,
        ).toBeLessThanOrEqual(1);
        if (touch) {
          await stop.tap();
        } else {
          await stop.click();
        }
      }

      await page.evaluate(() => window.__TC_TEST__?.pauseSim(false));
    }
  }
});

test('[INP-02] box selection selects exactly the own tanks in the box', async ({ page }) => {
  await enterGame(page);
  const own = (await units(page)).filter((unit) => unit.owner === 1);
  expect(own.length).toBe(4);
  const screens = await page.evaluate(
    (list) =>
      list.map((unit) => ({
        id: unit.id,
        screen: window.__TC_TEST__?.worldToScreen(unit.x, unit.z) ?? { x: 0, y: 0 },
      })),
    own.map((unit) => ({ id: unit.id, x: unit.x, z: unit.z })),
  );

  let chosen: { ids: number[]; start: { x: number; y: number }; end: { x: number; y: number } } | null =
    null;
  for (let i = 0; i < screens.length && !chosen; i += 1) {
    for (let j = i + 1; j < screens.length && !chosen; j += 1) {
      const a = screens[i];
      const b = screens[j];
      if (!a || !b) {
        continue;
      }
      const minX = Math.min(a.screen.x, b.screen.x) - 12;
      const maxX = Math.max(a.screen.x, b.screen.x) + 12;
      const minY = Math.min(a.screen.y, b.screen.y) - 12;
      const maxY = Math.max(a.screen.y, b.screen.y) + 12;
      const inside = screens.filter(
        (entry) =>
          entry.screen.x >= minX &&
          entry.screen.x <= maxX &&
          entry.screen.y >= minY &&
          entry.screen.y <= maxY,
      );
      if (inside.length === 2) {
        chosen = {
          ids: [a.id, b.id],
          start: { x: minX, y: minY },
          end: { x: maxX, y: maxY },
        };
      }
    }
  }
  expect(chosen).not.toBeNull();
  if (!chosen) {
    return;
  }
  await page.mouse.move(chosen.start.x, chosen.start.y);
  await page.mouse.down();
  await page.mouse.move(chosen.end.x, chosen.end.y, { steps: 6 });
  await page.mouse.up();
  await page.waitForTimeout(120);
  const selection = await page.evaluate(() => window.__TC_TEST__?.selection() ?? []);
  expect([...selection].sort((a, b) => a - b)).toEqual([...chosen.ids].sort((a, b) => a - b));
  const selectedUnits = (await units(page)).filter((unit) => unit.selected);
  expect(selectedUnits.every((unit) => unit.owner === 1)).toBe(true);
});

test('[INP-03] clicking an enemy with a selection lowers its HP', async ({ page }, testInfo) => {
  await enterGame(page);
  const touch = isTouch(testInfo);
  const all = await units(page);
  const own = all.filter((unit) => unit.owner === 1);
  const enemy = all.find((unit) => unit.owner === 2);
  const unit = own[0];
  expect(unit).toBeDefined();
  expect(enemy).toBeDefined();
  if (!unit || !enemy) {
    return;
  }
  const unitScreen = await page.evaluate(
    (id) => window.__TC_TEST__?.unitScreenCentre(id) ?? null,
    unit.id,
  );
  expect(unitScreen).not.toBeNull();
  if (!unitScreen) {
    return;
  }
  await selectUnit(page, unitScreen.x, unitScreen.y, touch);
  await expect.poll(async () => page.evaluate(() => window.__TC_TEST__?.selection() ?? [])).toContain(
    unit.id,
  );

  await setCamera(page, { targetX: enemy.x, targetZ: enemy.z, distance: 45, yaw: 0 });
  const enemyScreen = await page.evaluate(
    (id) => window.__TC_TEST__?.unitScreenCentre(id) ?? null,
    enemy.id,
  );
  expect(enemyScreen).not.toBeNull();
  if (!enemyScreen) {
    return;
  }
  await page.evaluate(() => window.__TC_TEST__?.setSimSpeed(8));
  await orderAt(page, enemyScreen.x, enemyScreen.y, touch);
  await expect
    .poll(
      async () => {
        const current = await units(page);
        return current.find((item) => item.id === enemy.id)?.hp ?? 0;
      },
      { timeout: 15000 },
    )
    .toBeLessThan(enemy.hp);
});

test('[INP-04] camera pan, zoom, rotate and edge clamping work', async ({ page }, testInfo) => {
  await enterGame(page);
  const touch = isTouch(testInfo);
  const start = await camera(page);

  if (touch) {
    await dispatchPointer(page, 'pointerdown', 1, 400, 300);
    await dispatchPointer(page, 'pointermove', 1, 500, 300);
    await dispatchPointer(page, 'pointerup', 1, 500, 300);
    await page.waitForTimeout(150);
    const panned = await camera(page);
    expect(Math.hypot(panned.targetX - start.targetX, panned.targetZ - start.targetZ)).toBeGreaterThan(0.1);

    const beforeZoom = await camera(page);
    await dispatchPointer(page, 'pointerdown', 2, 350, 300);
    await dispatchPointer(page, 'pointerdown', 3, 450, 300);
    await dispatchPointer(page, 'pointermove', 2, 300, 300);
    await dispatchPointer(page, 'pointermove', 3, 500, 300);
    await dispatchPointer(page, 'pointerup', 2, 300, 300);
    await dispatchPointer(page, 'pointerup', 3, 500, 300);
    await page.waitForTimeout(150);
    const zoomed = await camera(page);
    expect(Math.abs(zoomed.distance - beforeZoom.distance)).toBeGreaterThan(0.1);

    const beforeTwist = await camera(page);
    await dispatchPointer(page, 'pointerdown', 4, 350, 300);
    await dispatchPointer(page, 'pointerdown', 5, 450, 300);
    await dispatchPointer(page, 'pointermove', 5, 400, 250);
    await dispatchPointer(page, 'pointerup', 4, 350, 300);
    await dispatchPointer(page, 'pointerup', 5, 400, 250);
    await page.waitForTimeout(150);
    const twisted = await camera(page);
    expect(Math.abs(twisted.yaw - beforeTwist.yaw)).toBeGreaterThan(0.01);
  } else {
    await page.keyboard.down('w');
    await page.waitForTimeout(350);
    await page.keyboard.up('w');
    const panned = await camera(page);
    expect(Math.hypot(panned.targetX - start.targetX, panned.targetZ - start.targetZ)).toBeGreaterThan(0.1);

    const beforeZoom = await camera(page);
    await page.mouse.move(800, 400);
    await page.mouse.wheel(0, -500);
    await page.waitForTimeout(150);
    const zoomed = await camera(page);
    expect(zoomed.distance).toBeLessThan(beforeZoom.distance);

    const beforeRotate = await camera(page);
    await page.keyboard.down('e');
    await page.waitForTimeout(350);
    await page.keyboard.up('e');
    const rotated = await camera(page);
    expect(Math.abs(rotated.yaw - beforeRotate.yaw)).toBeGreaterThan(0.01);
  }

  await setCamera(page, { targetX: -79, targetZ: -79, distance: 40, yaw: 0 });
  if (touch) {
    for (let i = 0; i < 4; i += 1) {
      await dispatchPointer(page, 'pointerdown', 10 + i, 400, 300);
      await dispatchPointer(page, 'pointermove', 10 + i, 100, 100);
      await dispatchPointer(page, 'pointerup', 10 + i, 100, 100);
    }
  } else {
    await page.keyboard.down('a');
    await page.keyboard.down('w');
    await page.waitForTimeout(1200);
    await page.keyboard.up('a');
    await page.keyboard.up('w');
  }
  const clamped = await camera(page);
  expect(clamped.targetX).toBeGreaterThanOrEqual(-80);
  expect(clamped.targetX).toBeLessThanOrEqual(80);
  expect(clamped.targetZ).toBeGreaterThanOrEqual(-80);
  expect(clamped.targetZ).toBeLessThanOrEqual(80);
});

test('[INP-05] HUD button presses never issue map orders', async ({ page }, testInfo) => {
  await enterGame(page);
  const touch = isTouch(testInfo);
  const own = (await units(page)).filter((unit) => unit.owner === 1);
  const unit = own[0];
  expect(unit).toBeDefined();
  if (!unit) {
    return;
  }
  const unitScreen = await page.evaluate(
    (id) => window.__TC_TEST__?.unitScreenCentre(id) ?? null,
    unit.id,
  );
  expect(unitScreen).not.toBeNull();
  if (!unitScreen) {
    return;
  }
  await selectUnit(page, unitScreen.x, unitScreen.y, touch);
  await expect.poll(async () => page.evaluate(() => window.__TC_TEST__?.selection() ?? [])).toContain(
    unit.id,
  );

  const pause = page.getByRole('button', { name: 'Pause', exact: true });
  const stop = page.getByRole('button', { name: 'Stop', exact: true });
  const deselect = page.getByRole('button', { name: 'Deselect', exact: true });
  if (touch) {
    await stop.tap();
  } else {
    await stop.click();
  }
  await page.waitForTimeout(120);
  const afterStop = (await units(page)).find((item) => item.id === unit.id);
  expect(afterStop?.orderX).toBeNull();

  if (touch) {
    await deselect.tap();
  } else {
    await deselect.click();
  }
  await expect.poll(async () => page.evaluate(() => window.__TC_TEST__?.selection() ?? [])).toEqual([]);

  await selectUnit(page, unitScreen.x, unitScreen.y, touch);
  await expect.poll(async () => page.evaluate(() => window.__TC_TEST__?.selection() ?? [])).toContain(
    unit.id,
  );
  if (touch) {
    await pause.tap();
  } else {
    await pause.click();
  }
  await page.waitForFunction(() => window.__TC_TEST__?.screen() === 'pause');
  const selectionInPause = await page.evaluate(() => window.__TC_TEST__?.selection() ?? []);
  expect(selectionInPause).toContain(unit.id);
  const orderInPause = (await units(page)).find((item) => item.id === unit.id);
  expect(orderInPause?.orderX).toBeNull();
  await page.getByRole('button', { name: 'Resume', exact: true }).click();
  await page.waitForFunction(() => window.__TC_TEST__?.screen() === 'inGame');
});

test('[PLAY-01] full skirmish flow reaches results and Play again starts a fresh 4v4', async ({
  page,
}) => {
  // The spec allows up to 90 s of real time for the battle to resolve; the
  // project default (30 s) would kill the assertion before its own timeout.
  test.setTimeout(180_000);
  await enterGame(page);
  await page.evaluate(() => window.__TC_TEST__?.setSimSpeed(8));
  await page.evaluate(() => {
    const hook = window.__TC_TEST__;
    if (!hook) {
      return;
    }
    const current = hook.units();
    const own = current.filter((unit) => unit.owner === 1).map((unit) => unit.id);
    const enemy = current.find((unit) => unit.owner === 2);
    if (!enemy) {
      return;
    }
    hook.sendCommand({
      kind: 'attack',
      unitIds: own,
      targetId: enemy.id,
      tick: hook.snapshot().tick + 1,
      issuer: 1,
    });
  });
  await expect(page.locator('[data-screen-id="results"]')).toBeVisible({ timeout: 90_000 });
  const heading = await page.locator('[data-screen-id="results"] h1').textContent();
  expect(['Victory', 'Defeat', 'Draw']).toContain(heading ?? '');
  await page.getByRole('button', { name: 'Play again', exact: true }).click();
  await page.waitForFunction(() => window.__TC_TEST__?.screen() === 'inGame');
  await expect.poll(async () => (await units(page)).length).toBe(8);
});

test('[VIS-01] in-game screenshot is non-blank, colourful and shows eight units', async ({ page }) => {
  await enterGame(page);
  await expect
    .poll(async () => page.evaluate(() => window.__TC_TEST__?.renderStats().loadedModels ?? []))
    .toContain('unit.human.poc_tank');
  await expect
    .poll(async () => page.evaluate(() => window.__TC_TEST__?.renderStats().units ?? 0))
    .toBe(8);
  const canvas = page.locator('canvas');
  const screenshot = await canvas.screenshot();
  expect(countDistinctPngColors(screenshot)).toBeGreaterThan(20);
  const stats = await page.evaluate(() => window.__TC_TEST__?.renderStats());
  expect(stats?.units).toBe(8);
});
